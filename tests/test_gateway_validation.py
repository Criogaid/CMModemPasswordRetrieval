import unittest
from unittest.mock import patch

from main import ModemManager, is_host_reachable


class GatewayValidationTests(unittest.TestCase):
    def setUp(self):
        self.manager = ModemManager()
        self.manager.host = "192.168.1.1"

    def test_unreachable_host_stops_before_arp_lookup(self):
        with (
            patch("main.is_host_reachable", return_value=False),
            patch("main.subprocess.check_output") as arp_lookup,
            patch("builtins.input") as input_mock,
        ):
            mac_address = self.manager.get_mac_address()

        self.assertIsNone(mac_address)
        arp_lookup.assert_not_called()
        input_mock.assert_not_called()

    def test_ping_success_skips_tcp_fallback(self):
        with (
            patch("main.subprocess.run") as ping,
            patch("main.socket.create_connection") as tcp_connection,
        ):
            ping.return_value.returncode = 0
            self.assertTrue(is_host_reachable(self.manager.host))

        tcp_connection.assert_not_called()

    def test_tcp_port_80_is_used_when_ping_fails(self):
        with (
            patch("main.subprocess.run") as ping,
            patch("main.socket.create_connection") as tcp_connection,
        ):
            ping.return_value.returncode = 1
            self.assertTrue(is_host_reachable(self.manager.host))

        tcp_connection.assert_called_once_with((self.manager.host, 80), timeout=2)

    def test_reachability_fails_when_ping_and_tcp_fail(self):
        with (
            patch("main.subprocess.run") as ping,
            patch("main.socket.create_connection", side_effect=OSError("connection failed")),
        ):
            ping.return_value.returncode = 1
            self.assertFalse(is_host_reachable(self.manager.host))

    def test_missing_arp_entry_does_not_request_manual_mac(self):
        arp_result = (
            "Interface: 192.168.1.2 --- 0x7\n"
            "  Internet Address      Physical Address      Type\n"
            "  192.168.1.254         aa-bb-cc-dd-ee-ff     dynamic\n"
        )

        with (
            patch("main.is_host_reachable", return_value=True),
            patch("main.subprocess.check_output", return_value=arp_result.encode("utf-8")),
            patch("builtins.input") as input_mock,
        ):
            mac_address = self.manager.get_mac_address()

        self.assertIsNone(mac_address)
        input_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
