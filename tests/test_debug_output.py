import unittest
from unittest.mock import MagicMock, patch

from main import ModemManager


class DebugOutputTests(unittest.TestCase):
    def test_arp_output_is_logged_in_full(self):
        manager = ModemManager()
        manager.host = "192.168.0.1"
        arp_result = (
            "Interface: 192.168.0.2 --- 0x7\n"
            "  Internet Address      Physical Address      Type\n"
            "  192.168.0.1           ff-ff-ff-ff-ff-ff     dynamic\n"
        )

        with (
            patch("main.is_host_reachable", return_value=True),
            patch("main.subprocess.check_output", return_value=arp_result.encode("utf-8")),
            patch("main.logger.debug") as debug_log,
        ):
            mac_address = manager.get_mac_address()

        self.assertEqual(mac_address, "FFFFFFFFFFFF")
        debug_log.assert_called_once_with(f"ARP Result:\n{arp_result}")

    def test_factory_telnet_output_is_logged_before_parse_failure(self):
        manager = ModemManager()
        manager.method = 0
        manager.host = "192.168.0.1"
        manager.mac_address = "FFFFFFFFFFFF"
        telnet_result = "unparseable factory response"
        telnet = MagicMock()
        telnet.__enter__.return_value = telnet
        telnet.read_all.return_value = telnet_result.encode("ascii")

        with (
            patch("main.telnetlib.Telnet", return_value=telnet),
            patch("main.logger.debug") as debug_log,
        ):
            result = manager.get_admin_password()

        self.assertIsNone(result)
        debug_log.assert_any_call(f"Telnet Result:\n{telnet_result}")

    def test_cli_telnet_output_is_logged_before_parse_failure(self):
        manager = ModemManager()
        manager.method = 1
        manager.host = "192.168.0.1"
        manager.mac_address = "FFFFFFFFFFFF"
        telnet_result = "unparseable CLI response"
        telnet = MagicMock()
        telnet.__enter__.return_value = telnet
        telnet.read_all.return_value = telnet_result.encode("utf-8")

        with (
            patch("main.telnetlib.Telnet", return_value=telnet),
            patch("main.time.sleep"),
            patch("main.logger.debug") as debug_log,
        ):
            result = manager.get_admin_password()

        self.assertIsNone(result)
        debug_log.assert_any_call(f"Telnet Result:\n{telnet_result}")


if __name__ == "__main__":
    unittest.main()
