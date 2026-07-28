import os
import json
import re
import socket
import subprocess
import sys
import telnetlib
import time

import requests
from loguru import logger


HOST_PATTERN = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
MAC_PATTERN = re.compile(r"^[0-9A-F]{12}$")


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
    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

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

    datenow = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({
            "date": datenow,
            "host": host,
            "mac_address": mac_address,
        }, f, ensure_ascii=False, indent=2)
    return datenow


def clear_console():
    rows, columns = os.get_terminal_size()
    print("\n" * rows, end="")


def obtain_value_from_text(text):
    lines_to_return = []

    if text is None:
        return lines_to_return

    # 正则表达式匹配以 "get success!value=" 开头的行
    pattern = re.compile(r'^get success!value=.*$')

    # 将输入的文本按行处理
    for line in text.splitlines():
        line = line.strip()
        if line and pattern.match(line):
            lines_to_return.append(line)

    return lines_to_return


class ModemManager:
    def __init__(self):
        self.host = ""
        self.port = 23
        self.mac_address = ""
        self.host = ""
        self.method = ""

    def set_host(self):
        host = input("Please enter the IP address of the modem (default:192.168.0.1): ") or "192.168.0.1"
        if not validate_host(host):
            raise ValueError("Invalid host address.")
        self.host = host.strip()
        logger.info(f"Host set to: {self.host}")
        return self.host

    def get_mac_address(self):
        # ICMP 探测也会促使 Windows 刷新目标 IP 的 ARP 条目。
        if not is_host_reachable(self.host):
            logger.error(f"Host {self.host} is unreachable.")
            return None

        try:
            arp_output = subprocess.check_output("arp -a", shell=True)
            arp_result = arp_output.decode('utf-8')
        except UnicodeDecodeError:
            arp_result = arp_output.decode('gbk')
        except Exception as e:
            logger.error(f"Please Check your host address or Send the following error to the author:\r\n{e}")
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

    def enable_telnet(self):
        url = f"http://{self.host}/cgi-bin/telnetenable.cgi?telnetenable=1&key={self.mac_address}"
        logger.debug(f"Telnet Enable URL: {url}")
        try:
            response = requests.get(url, timeout=5)
        except (requests.exceptions.Timeout, requests.exceptions.RequestException):
            logger.error("Failed to enable Telnet.")
            return False
        if "if (1 == 1)" in response.text or "telnet开启" in response.text:
            logger.info("Telnet has been successfully enabled.")
            self.method = 0 if "if (1 == 1)" in response.text else 1
            return True
        else:
            logger.error("Failed to enable Telnet.")
            return False

    def get_admin_password(self):
        admin_password = None
        admin_username = None
        if self.method == 0:
            username = "root"
            password = f"Fh@{self.mac_address[-6:]}"
            logger.debug(f"Using Username: {username}")
            logger.debug(f"Using Password: {password}")
            try:
                with telnetlib.Telnet(self.host, self.port) as tn:
                    tn.read_until(b"login: ")
                    tn.write(username.encode('ascii') + b"\n")
                    tn.read_until(b"Password: ")
                    tn.write(password.encode('ascii') + b"\n")
                    tn.write(b"cat /flash/cfg/agentconf/factory.conf\n")
                    tn.write(b"exit\n")
                    result = tn.read_all().decode('ascii')
            except Exception as e:
                logger.error(f"Telnet connection failed: {e}")
                return None
            logger.debug(f"Telnet Result:\n{result}")
            try:
                admin_username = re.search(r'TelecomAccount=(.*)', result).group(1).strip()
                admin_password = re.search(r'TelecomPasswd=(.*)', result).group(1).strip()
            except AttributeError as e:
                logger.error(f"Failed to parse factory.conf: {e}")
                return None
        elif self.method == 1:
            username = "admin"
            password = f"Fh@{self.mac_address[-6:]}"
            logger.debug(f"Using Username: {username}")
            logger.debug(f"Using Password: {password}")
            try:
                with telnetlib.Telnet(self.host, self.port) as tn:
                    tn.read_until(b"login:")
                    tn.write(username.encode('utf-8') + b"\n")
                    tn.read_until(b"Password:")
                    tn.write(password.encode('utf-8') + b"\n")
                    time.sleep(0.5)
                    tn.write(b"load_cli factory\n")
                    time.sleep(0.5)
                    tn.write(b"show admin_pwd\n")
                    time.sleep(0.5)
                    tn.write(b"show admin_name\n")
                    time.sleep(0.5)
                    tn.write(b"exit\n")
                    time.sleep(0.5)
                    tn.write(b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Username\n")
                    time.sleep(0.5)
                    tn.write(b"cfg_cmd get InternetGatewayDevice.DeviceInfo.X_CMCC_TeleComAccount.Password\n")
                    time.sleep(0.5)
                    tn.write(b"exit\n")
                    result = tn.read_all().decode('utf-8')
            except Exception as e:
                logger.error(f"Telnet connection failed: {e}")
                return None
            logger.debug(f"Telnet Result:\n{result}")
            try:
                admin_username = re.search(r'admin_name=(.*)', result).group(1).strip()
                admin_password = re.search(r'admin_pwd=(.*)', result).group(1).strip()
            except AttributeError as e:
                logger.error(f"Failed to obtain Admin Username and Password form factory mode: {e}")
                if "Unknown command" in result:
                    logger.debug("Entering experimental mode. This mode is based on tutorial methods and has not been fully tested. If you successfully retrieve the results, please provide feedback to the author via an issue report.")
                    obtain_result = obtain_value_from_text(result)
                    if isinstance(obtain_result, list) and len(obtain_result) == 2:
                        admin_username = obtain_result[0]
                        admin_password = obtain_result[1]
                    else:
                        logger.error("Experimental mode failed.")
                        return None
                else:
                    return None
        return admin_username, admin_password

    def manage_modem(self):
        if self.enable_telnet():
            return self.get_admin_password()
        else:
            return False

    def main(self):
        ConfigFile=os.path.join(sys.path[0],'CMCCModelConfig.json')
        '''Configuration file CMCCModelConfig.json
        {
            "date":"1970-1-1 00:00:00",
            "host":"182.168.0.1",
            "mac_address":"ffffffffffff"
        }
        '''
        readconfig=False
        if os.path.exists(ConfigFile):
            if is_yes_response(input("Do you want to use the old Configuration file? [Y/Others] ")):
                logger.info(f"Reading Config...")
                try:
                    Config = load_config(ConfigFile)
                    self.host = Config["host"]
                    logger.info(f"Last Config: {ConfigFile} on {Config['date']}")
                    readconfig=True
                except Exception:
                    logger.error(f"Failed to read configuration. Please delete: {ConfigFile} and try again. Error details below:")
                    raise
        if readconfig==False:
            self.host = self.set_host()
        self.mac_address = self.get_mac_address()
        if not self.mac_address:
            logger.error("Cannot continue without a reachable host and a valid ARP entry.")
            exit(0)
        data = self.manage_modem()
        if isinstance(data, tuple) and len(data) == 2 and all(data):
            logger.info(f"Sucessfully obtained Admin Username and Password for {self.host}!")
            logger.info(f"Username: {data[0]}")
            logger.info(f"Password: {data[1]}")
        else:
            logger.error("Failed to obtain Admin Username and Password.")
            logger.info(
                "Please follow the manual confirmation steps at "
                "`https://www.bilibili.com/read/cv21044770/` and modify the code if necessary.")
            exit(0)
        if self.host and self.mac_address and is_yes_response(input("Do you want to save the configuration? [Y/Others] ")):
            try:
                datenow = save_config(ConfigFile, self.host, self.mac_address)
                logger.info(f"Save Config: {ConfigFile} on {datenow}")
            except Exception:
                logger.error(f"Failed to write configuration. Please check read/write permissions for {ConfigFile} .Error details below:")
                raise
        exit(0)


if __name__ == "__main__":
    manager = ModemManager()
    manager.main()
