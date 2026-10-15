import unittest
from unittest.mock import MagicMock, patch

from main import SHELL_PROMPT, get_mac_address, read_telnet_response


class DebugOutputTests(unittest.TestCase):
    def test_arp_output_is_logged_in_full(self):
        arp_result = (
            "Interface: 192.168.0.2 --- 0x7\n"
            "  Internet Address      Physical Address      Type\n"
            "  192.168.0.1           ff-ff-ff-ff-ff-ff     dynamic\n"
        )

        with (
            patch("main.is_host_reachable", return_value=True),
            patch(
                "main.subprocess.check_output", return_value=arp_result.encode("utf-8")
            ),
            patch("main.logger.debug") as debug_log,
        ):
            mac_address = get_mac_address("192.168.0.1")

        self.assertEqual(mac_address, "FFFFFFFFFFFF")
        debug_log.assert_called_once_with(f"ARP Result:\n{arp_result}")

    def test_telnet_output_is_logged_before_missing_prompt_error(self):
        telnet_result = "unparseable device response"
        telnet = MagicMock()
        telnet.eof = False
        telnet.expect.return_value = (-1, None, telnet_result.encode("utf-8"))

        with patch("main.logger.debug") as debug_log, self.assertRaises(TimeoutError):
            read_telnet_response(telnet, SHELL_PROMPT)

        debug_log.assert_any_call(f"Telnet Result:\n{telnet_result}")


if __name__ == "__main__":
    unittest.main()
