import requests
import re
import subprocess
import telnetlib
from loguru import logger


class ModemManager:
    def __init__(self, host="192.168.0.1", port=23):
        self.host = host
        self.port = port
        self.mac_address = self.get_mac_address()

    def set_host(self):
        self.host = input(
            "Please enter the IP address of the modem (default:192.168.0.1): ") or self.host
        logger.info(f"Host set to: {self.host}")
        return self.host

    def get_mac_address(self):
        arp_result = subprocess.check_output("arp -a", shell=True).decode('gbk')
        mac_address = [re.split(r'\s+', line)[2] for line in arp_result.split("\n") if self.host in line][0]
        if mac_address:
            logger.info(f"MAC Address obtained successfully: {mac_address}")
        else:
            logger.error("Failed to obtain MAC Address.")
        return mac_address.upper().replace("-", "")

    def enable_telnet(self):
        url = f"http://{self.host}/cgi-bin/telnetenable.cgi?telnetenable=1&key={self.mac_address}"
        logger.debug(f"Telnet Enable URL: {url}")
        response = requests.get(url)
        if "if (1 == 1)" in response.text:
            logger.info("Telnet has been successfully enabled.")
            return True
        else:
            logger.error("Failed to enable Telnet.")
            return False

    def get_admin_password(self):
        password = f"Fh@{self.mac_address[-6:]}"
        logger.debug(f"Using password: {password}")
        tn = telnetlib.Telnet(self.host, self.port)
        tn.read_until(b"login: ")
        tn.write(b"root\n")
        tn.read_until(b"Password: ")
        tn.write(password.encode('ascii') + b"\n")
        tn.write(b"cat /flash/cfg/agentconf/factory.conf\n")
        tn.write(b"exit\n")
        result = tn.read_all().decode('ascii')
        admin_password = re.search(r'TelecomPasswd=(.*)', result).group(1).strip()
        logger.debug(f"factory.conf: {result}")
        logger.info(f"Admin Password obtained successfully: {admin_password}")
        return admin_password

    def manage_modem(self):
        if self.enable_telnet():
            return self.get_admin_password()
        else:
            logger.error(
                "Please follow the manual confirmation steps at  `https://www.bilibili.com/read/cv21044770/` and modify the code if necessary.")
            return False


if __name__ == "__main__":
    manager = ModemManager()
    manager.set_host()
    admin_password = manager.manage_modem()
