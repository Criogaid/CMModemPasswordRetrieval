import json
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Optional

import requests
from loguru import logger

# Python 3.13 移除了标准库 telnetlib；旧版继续使用内置实现。
if sys.version_info >= (3, 13):
    from telnetlib3.telnetlib import Telnet
else:
    from telnetlib import Telnet


HOST_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)
MAC_PATTERN = re.compile(r"^[0-9A-F]{12}$")
# Keep the discovery order in sync with README.md under "运行".
DEFAULT_HOSTS = ("192.168.0.1", "192.168.1.1")
HTTP_TIMEOUT_SECONDS = 5
TELNET_TIMEOUT_SECONDS = 5
LOGIN_PROMPT = re.compile(rb"login:\s*", re.IGNORECASE)
PASSWORD_PROMPT = re.compile(rb"password:\s*", re.IGNORECASE)
# Exclude assignments so a password ending in '#' is not mistaken for a prompt.
SHELL_PROMPT = re.compile(rb"(?m)^[^\r\n=]*[#$>][ \t]*\r?$")


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str

    @property
    def complete(self) -> bool:
        return bool(self.username and self.password)


def is_yes_response(response):
    return isinstance(response, str) and response.strip().casefold() == "y"


def validate_host(host):
    return isinstance(host, str) and bool(HOST_PATTERN.fullmatch(host.strip()))


def is_host_reachable(host):
    if not validate_host(host):
        return False

    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1500", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        logger.debug(f"Ping reachability check failed: {error}")
    else:
        if result.returncode == 0:
            return True

    # TCP 80 是后续启用 Telnet 所依赖的实际通信路径，可兼容禁用 ICMP 的设备。
    try:
        with socket.create_connection((host, 80), timeout=2):
            return True
    except OSError as error:
        logger.debug(f"TCP port 80 reachability check failed: {error}")
        return False


def normalize_mac_address(mac_address):
    if not isinstance(mac_address, str):
        return None

    normalized = mac_address.strip().upper().replace("-", "").replace(":", "")
    if not MAC_PATTERN.fullmatch(normalized):
        return None
    return normalized


def load_config(config_file):
    with open(config_file, "r", encoding="utf-8") as config_handle:
        config = json.load(config_handle)

    host = str(config.get("host", "")).strip()
    mac_address = normalize_mac_address(config.get("mac_address", ""))
    if not validate_host(host) or not mac_address:
        raise ValueError("Invalid host or MAC address in configuration file.")

    return {
        "date": config.get("date", "unknown"),
        "host": host,
        "mac_address": mac_address,
    }


def save_config(config_file, host, mac_address):
    host = host.strip() if isinstance(host, str) else ""
    mac_address = normalize_mac_address(mac_address)
    if not validate_host(host) or not mac_address:
        raise ValueError("Cannot save invalid host or MAC address.")

    saved_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(config_file, "w", encoding="utf-8") as config_handle:
        json.dump({
            "date": saved_at,
            "host": host,
            "mac_address": mac_address,
        }, config_handle, ensure_ascii=False, indent=2)
    return saved_at


def read_telnet_response(telnet: Telnet, prompt: re.Pattern[bytes]) -> str:
    index, _, data = telnet.expect([prompt], timeout=TELNET_TIMEOUT_SECONDS)
    result = data.decode("utf-8", errors="replace")
    logger.debug(f"Telnet Result:\n{result}")
    if index < 0:
        if telnet.eof:
            raise EOFError("Telnet closed before returning the expected prompt.")
        raise TimeoutError("Telnet closed or did not return the expected prompt.")
    return result


def confirm_telnet_interactive(telnet: Telnet) -> None:
    telnet.write(b"\n")
    read_telnet_response(telnet, SHELL_PROMPT)


def run_telnet_command(telnet: Telnet, command: bytes) -> str:
    telnet.write(command + b"\n")
    try:
        return read_telnet_response(telnet, SHELL_PROMPT)
    except TimeoutError:
        logger.warning(
            "Command response timed out; waiting once for completion before checking CLI interaction."
        )
        # Drain the original command's prompt before creating another with an empty line.
        read_telnet_response(telnet, SHELL_PROMPT)
        confirm_telnet_interactive(telnet)
        # A recovered prompt does not make an incomplete command response usable.
        return ""


def read_response_field(response: str, field: str) -> str:
    match = re.search(
        rf"(?m)^[ \t]*(?:Success![ \t]*)?{re.escape(field)}=([^\r\n]*)",
        response,
    )
    return match.group(1).strip() if match else ""


def read_factory_config(telnet: Telnet) -> Credentials:
    result = run_telnet_command(telnet, b"cat /flash/cfg/agentconf/factory.conf")
    return Credentials(
        read_response_field(result, "TelecomAccount"),
        read_response_field(result, "TelecomPasswd"),
    )


def read_factory_cli(telnet: Telnet) -> Credentials:
    run_telnet_command(telnet, b"load_cli factory")
    username = read_response_field(
        run_telnet_command(telnet, b"show admin_name"), "admin_name"
    )
    password = read_response_field(
        run_telnet_command(telnet, b"show admin_pwd"), "admin_pwd"
    )
    return Credentials(username, password)


def read_cfg_cmd(telnet: Telnet) -> Credentials:
    path = b"InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount"
    username = read_response_field(
        run_telnet_command(telnet, b"cfg_cmd get " + path + b".Username"),
        "get success!value",
    )
    password = read_response_field(
        run_telnet_command(telnet, b"cfg_cmd get " + path + b".Password"),
        "get success!value",
    )
    return Credentials(username, password)


class ModemManager:
    def __init__(self):
        self.host = ""
        self.port = 23
        self.mac_address = ""

    def set_host(self) -> str:
        """Return the supplied IPv4 address, or an empty string for auto-detection."""
        host = input(
            f"Enter the modem IPv4 address (Enter to try {' then '.join(DEFAULT_HOSTS)}): "
        ).strip()
        if host and not validate_host(host):
            raise ValueError("Invalid host address.")
        self.host = host
        return self.host

    def get_mac_address(self):
        # 主动探测会促使 Windows 刷新目标 IP 的 ARP 条目。
        if not is_host_reachable(self.host):
            logger.error(f"Host {self.host} is unreachable.")
            return None

        try:
            arp_output = subprocess.check_output("arp -a", shell=True)
            arp_result = arp_output.decode('utf-8')
        except UnicodeDecodeError:
            arp_result = arp_output.decode('gbk')
        except Exception as error:
            logger.error(f"Please Check your host address or Send the following error to the author:\r\n{error}")
            return None
        if not arp_result:
            logger.error("Failed to obtain ARP table.")
            return None
        logger.debug(f"ARP Result:\n{arp_result}")
        lines = arp_result.split("\n")
        for line in lines:
            fields = re.split(r'\s+', line.strip())
            if not fields or fields[0] != self.host:
                continue

            for field in fields[1:]:
                normalized_mac_address = normalize_mac_address(field)
                if normalized_mac_address:
                    logger.info(f"MAC Address obtained successfully: {normalized_mac_address}")
                    return normalized_mac_address

            logger.error(f"Invalid ARP table entry: {line.strip()}")
            return None

        logger.error(f"No ARP entry found for host {self.host}.")
        return None

    def enable_telnet(self) -> bool:
        url = f"http://{self.host}/cgi-bin/telnetenable.cgi?telnetenable=1&key={self.mac_address}"
        logger.debug(f"Telnet Enable URL: {url}")
        try:
            response = requests.get(
                url, timeout=HTTP_TIMEOUT_SECONDS, allow_redirects=False
            )
        except requests.exceptions.RequestException as error:
            logger.error(f"Telnet enable request failed: {error}")
            return False
        if response.status_code != HTTPStatus.OK:
            logger.error(
                f"Telnet enable request returned HTTP {response.status_code}; stopping."
            )
            return False
        try:
            with socket.create_connection(
                (self.host, self.port), timeout=TELNET_TIMEOUT_SECONDS
            ):
                pass
        except OSError as error:
            logger.error(
                f"Cannot connect to Telnet at {self.host}:{self.port}: {error}"
            )
            return False
        logger.info(
            "Telnet enable request returned HTTP 200 and the Telnet port is reachable."
        )
        return True

    def get_admin_password(self) -> Optional[Credentials]:
        password = f"Fh@{self.mac_address[-6:]}"
        partial = None
        readers = (
            ("factory.conf", read_factory_config),
            ("cfg_cmd", read_cfg_cmd),
            ("factory CLI", read_factory_cli),
        )
        for username in ("root", "admin"):
            logger.info(f"Trying Telnet user {username}.")
            try:
                with Telnet(
                    self.host, self.port, timeout=TELNET_TIMEOUT_SECONDS
                ) as telnet:
                    read_telnet_response(telnet, LOGIN_PROMPT)
                    telnet.write(username.encode("ascii") + b"\n")
                    read_telnet_response(telnet, PASSWORD_PROMPT)
                    telnet.write(password.encode("ascii") + b"\n")
                    read_telnet_response(telnet, SHELL_PROMPT)
                    confirm_telnet_interactive(telnet)
                    logger.info(f"Interactive CLI confirmed for {username}.")
                    for reader_name, reader in readers:
                        logger.info(
                            f"Trying {reader_name} in the existing {username} session."
                        )
                        credentials = reader(telnet)
                        if credentials.complete:
                            logger.info(
                                f"Retrieved administrator credentials using {username} with {reader_name}."
                            )
                            return credentials
                        if credentials.password or (
                            credentials.username and partial is None
                        ):
                            partial = credentials
                        logger.debug(
                            f"No complete credentials returned by {reader_name}."
                        )
            except (OSError, EOFError) as error:
                logger.warning(f"Telnet session ended for {username}: {error}")
        if partial is None:
            logger.error("No Telnet username and retrieval method succeeded.")
        return partial

    def manage_modem(self) -> Optional[Credentials]:
        if self.enable_telnet():
            return self.get_admin_password()
        return None

    def main(self):
        config_file = os.path.join(sys.path[0], "CMCCModelConfig.json")
        config_loaded = False
        if os.path.exists(config_file):
            if is_yes_response(input("Do you want to use the old Configuration file? [Y/Others] ")):
                logger.info("Reading Config...")
                try:
                    config = load_config(config_file)
                    self.host = config["host"]
                    self.mac_address = config["mac_address"]
                    logger.info(f"Last Config: {config_file} on {config['date']}")
                    config_loaded = True
                except Exception:
                    logger.error(f"Failed to read configuration. Please delete: {config_file} and try again. Error details below:")
                    raise
        if not config_loaded:
            host = self.set_host()
            for candidate in (host,) if host else DEFAULT_HOSTS:
                self.host = candidate
                logger.info(f"Checking modem at {self.host}.")
                self.mac_address = self.get_mac_address()
                if self.mac_address:
                    break
            if not self.mac_address:
                logger.error("Cannot continue without a reachable host and a valid ARP entry.")
                exit(0)
        credentials = self.manage_modem()
        if credentials is not None:
            if credentials.complete:
                logger.info(
                    f"Successfully obtained Admin Username and Password for {self.host}!"
                )
            else:
                logger.warning("Only partial administrator credentials were retrieved.")
            if credentials.username:
                logger.info(f"Username: {credentials.username}")
            else:
                logger.warning("Username: unconfirmed")
            if credentials.password:
                logger.info(f"Password: {credentials.password}")
            else:
                logger.warning("Password: unconfirmed")
            if not credentials.complete:
                exit(0)
        else:
            logger.error("Failed to obtain Admin Username and Password.")
            logger.info(
                "Please follow the manual confirmation steps at "
                "`https://www.bilibili.com/read/cv21044770/` and modify the code if necessary.")
            exit(0)
        if self.host and self.mac_address and is_yes_response(input("Do you want to save the configuration? [Y/Others] ")):
            try:
                saved_at = save_config(config_file, self.host, self.mac_address)
                logger.info(f"Save Config: {config_file} on {saved_at}")
            except Exception:
                logger.error(f"Failed to write configuration. Please check read/write permissions for {config_file}. Error details below:")
                raise
        exit(0)


if __name__ == "__main__":
    manager = ModemManager()
    manager.main()
