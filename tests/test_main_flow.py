import unittest
from unittest.mock import patch

from main import ModemManager


class MainFlowTests(unittest.TestCase):
    def test_retrieval_failure_exits_without_prompting_to_save(self):
        for failed_result in (False, None, (None, None), ("", "")):
            with self.subTest(failed_result=failed_result):
                manager = ModemManager()
                with (
                    patch("main.os.path.exists", return_value=False),
                    patch.object(manager, "set_host", return_value="192.168.0.1"),
                    patch.object(manager, "get_mac_address", return_value="FFFFFFFFFFFF"),
                    patch.object(manager, "manage_modem", return_value=failed_result),
                    patch("builtins.input") as input_mock,
                ):
                    with self.assertRaises(SystemExit) as raised:
                        manager.main()

                self.assertEqual(raised.exception.code, 0)
                input_mock.assert_not_called()

    def test_success_still_prompts_to_save(self):
        manager = ModemManager()
        with (
            patch("main.os.path.exists", return_value=False),
            patch.object(manager, "set_host", return_value="192.168.0.1"),
            patch.object(manager, "get_mac_address", return_value="FFFFFFFFFFFF"),
            patch.object(manager, "manage_modem", return_value=("admin", "password")),
            patch("builtins.input", return_value="n") as input_mock,
        ):
            with self.assertRaises(SystemExit) as raised:
                manager.main()

        self.assertEqual(raised.exception.code, 0)
        input_mock.assert_called_once_with("Do you want to save the configuration? [Y/Others] ")

    def test_missing_mac_exits_before_modem_management(self):
        manager = ModemManager()
        with (
            patch("main.os.path.exists", return_value=False),
            patch.object(manager, "set_host", return_value="192.168.0.1"),
            patch.object(manager, "get_mac_address", return_value=None),
            patch.object(manager, "manage_modem") as manage_modem,
            patch("builtins.input") as input_mock,
        ):
            with self.assertRaises(SystemExit) as raised:
                manager.main()

        self.assertEqual(raised.exception.code, 0)
        manage_modem.assert_not_called()
        input_mock.assert_not_called()

    def test_loaded_config_skips_network_validation(self):
        manager = ModemManager()
        with (
            patch("main.os.path.exists", return_value=True),
            patch("main.load_config", return_value={
                "date": "2026-01-01 00:00:00",
                "host": "192.168.0.1",
                "mac_address": "AAAAAAAAAAAA",
            }),
            patch.object(manager, "get_mac_address") as get_mac_address,
            patch.object(manager, "manage_modem", return_value=("admin", "password")),
            patch("builtins.input", side_effect=["y", "n"]),
        ):
            with self.assertRaises(SystemExit) as raised:
                manager.main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(manager.mac_address, "AAAAAAAAAAAA")
        get_mac_address.assert_not_called()


if __name__ == "__main__":
    unittest.main()
