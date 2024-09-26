import os
import re
import subprocess
import telnetlib
import time

import requests
from loguru import logger


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
        if not isinstance(host, str):
            raise TypeError("Host address must be a string.")
        if not host:
            raise ValueError("Host address must not be empty.")
        if not re.match(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", host):
            raise ValueError("Invalid host address.")
        self.host = host
        logger.info(f"Host set to: {self.host}")
        return self.host

    def get_mac_address(self):
        try:
            arp_result = subprocess.check_output("arp -a", shell=True).decode('utf-8')
        except UnicodeDecodeError:
            arp_result = subprocess.check_output("arp -a", shell=True).decode('gbk')
        except Exception as e:
            logger.error(f"Please Check your host address or Send the following error to the author:\r\n{e}")
            exit(0)
        if not arp_result:
            logger.error("Failed to obtain ARP table.")
            return None
        logger.debug(arp_result)
        lines = arp_result.split("\n")
        for line in lines:
            line = line.strip()
            if self.host + " " in line and "---" not in line:
                fields = re.split(r'\s+', line)
                if len(fields) < 3:
                    logger.error(f"Invalid ARP table entry: {line}")
                    return None
                mac_address = next((item for item in fields if "-" in item), None)
                break
        else:
            logger.error(f"Failed to obtain MAC address from ARP table for host {self.host}")
            return None
        if not mac_address:
            logger.error("Failed to obtain MAC address.")
            return None
        mac_address = mac_address.upper().replace("-", "")
        logger.info(f"MAC Address obtained successfully: {mac_address}")
        return mac_address

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
            try:
                admin_username = re.search(r'TelecomAccount=(.*)', result).group(1).strip()
                admin_password = re.search(r'TelecomPasswd=(.*)', result).group(1).strip()
            except AttributeError as e:
                logger.error(f"Failed to parse factory.conf: {e}")
                return None
            logger.debug(f"factory.conf: {result}")
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
            logger.debug(f"Telenet Result: {result}")
        return admin_username, admin_password

    def manage_modem(self):
        if self.enable_telnet():
            return self.get_admin_password()
        else:
            return False

    def main(self):
        self.host = self.set_host()
        self.mac_address = self.get_mac_address()
        data = self.manage_modem()
        if isinstance(data, tuple) and data:
            clear_console()
            logger.info(f"Sucessfully obtained Admin Username and Password for {self.host}!")
            logger.info(f"Username: {data[0]}")
            logger.info(f"Password: {data[1]}")
        else:
            logger.error("Failed to obtain Admin Username and Password.")
            logger.info(
                "Please follow the manual confirmation steps at "
                "`https://www.bilibili.com/read/cv21044770/` and modify the code if necessary.")
            exit(0)


if __name__ == "__main__":
    manager = ModemManager()
    manager.main()
