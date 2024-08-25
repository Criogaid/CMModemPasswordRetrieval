import os
import re
import subprocess
import telnetlib
import time

import requests
from loguru import logger


class ModemManager:
    def __init__(self):
        self.host = ""
        self.port = 23
        self.mac_address = ""
        self.host = ""
        self.method = ""

    def set_host(self):
        host = input("Please enter the IP address of the modem (default:192.168.0.1): ") or "192.168.0.1"
        self.host = host
        logger.info(f"Host set to: {self.host}")
        return self.host

    def get_mac_address(self):
        try:
            arp_result = subprocess.check_output("arp -a", shell=True).decode('utf-8')

            mac_address = [re.split(r'\s+', line)[2] for line in arp_result.split("\n") if self.host + " "
                           in line][0]
        except Exception as e:
            print("-" * 100)
            print("Please Check your host address")
            exit(0)
        if mac_address:
            logger.info(f"MAC Address obtained successfully: {mac_address}")
        else:
            logger.error("Failed to obtain MAC Address.")
        return mac_address.upper().replace("-", "")

    def enable_telnet(self):
        url = f"http://{self.host}/cgi-bin/telnetenable.cgi?telnetenable=1&key={self.mac_address}"
        logger.debug(f"Telnet Enable URL: {url}")
        try:
            response = requests.get(url)
            logger.debug(f"check your IP Address: {self.host}")
        except Exception as e:
            print(e)
            exit(0)
        if "if (1 == 1)" in response.text:
            logger.info("Telnet has been successfully enabled.")
            self.method = 0
            return True
        elif "telnet开启" in response.text:
            logger.info("Telnet has been successfully enabled.")
            self.method = 1
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
            print(password)
            logger.debug(f"Using Username: {username}")
            logger.debug(f"Using Password: {password}")
            tn = telnetlib.Telnet(self.host, self.port)
            tn.read_until(b"login: ")
            tn.write(username.encode('ascii') + b"\n")
            tn.read_until(b"Password: ")
            tn.write(password.encode('ascii') + b"\n")
            tn.write(b"cat /flash/cfg/agentconf/factory.conf\n")
            tn.write(b"exit\n")
            result = tn.read_all().decode('ascii')
            admin_password = re.search(r'TelecomPasswd=(.*)', result).group(1).strip()
            logger.debug(f"factory.conf: {result}")
            logger.info(f"Admin Password obtained successfully: {admin_password}")
        elif self.method == 1:
            username = "admin"
            password = f"Fh@{self.mac_address[-6:]}"
            logger.debug(f"Using Username: {username}")
            logger.debug(f"Using Password: {password}")
            tn = telnetlib.Telnet(self.host, self.port)
            tn.read_until(b"login:")
            tn.write(username.encode('utf-8') + b"\n")
            tn.read_until(b"Password:")
            tn.write(password.encode('utf-8') + b"\n")
            time.sleep(1)
            tn.write(b"load_cli factory\n")
            time.sleep(1)
            tn.write(b"show admin_pwd\n")
            time.sleep(1)
            tn.write(b"show admin_name\n")
            time.sleep(1)
            tn.write(b"exit\n")
            tn.write(b"exit\n")
            result = tn.read_all().decode('utf-8')
            # tn.write(b"exit\n")
            admin_username = re.search(r'admin_name=(.*)', result).group(1).strip()
            admin_password = re.search(r'admin_pwd=(.*)', result).group(1).strip()
            logger.debug(f"factory.conf: {result}")
            logger.info(f"Admin Username and Password obtained successfully: \nusername: {admin_username}"
                        f"\npassword: {admin_password}")
        return admin_username, admin_password

    def manage_modem(self):
        if self.enable_telnet():
            data = self.get_admin_password()
            print()
            return f"{"-" * 120}\nUsername/login: {data[0]}\nPassword: {data[1]}"
        else:
            logger.error(
                "Please follow the manual confirmation steps at  "
                "`https://www.bilibili.com/read/cv21044770/` and modify the code if necessary.")
            return False

    def cls(self):
        os.system("cls" if os.name == "nt" else "clear")

    def main(self):
        self.host = self.set_host()
        self.mac_address = self.get_mac_address()
        data = self.manage_modem()
        self.cls()
        print(f"\nSucessfully set got Username/Login and Password!\n{data}\n")


if __name__ == "__main__":
    manager = ModemManager()
    manager.main()
