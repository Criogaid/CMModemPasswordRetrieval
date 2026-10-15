import unittest
from unittest.mock import patch

from main import ModemManager


class MainFlowTests(unittest.TestCase):
    def test_empty_address_tries_defaults_in_order_and_stops_on_success(self):
        cases = (
            (["AABBCCDDEEFF"], ["192.168.0.1"]),
            ([None, "AABBCCDDEEFF"], ["192.168.0.1", "192.168.1.1"]),
            ([None, None], ["192.168.0.1", "192.168.1.1"]),
        )
        for mac_results, expected_hosts in cases:
            with self.subTest(mac_results=mac_results):
                manager = ModemManager()
                checked_hosts = []
                results = iter(mac_results)

                def get_mac():
                    checked_hosts.append(manager.host)
                    return next(results)

                with (
                    patch("main.os.path.exists", return_value=False),
                    patch("builtins.input", side_effect=["", "n"]) as input_mock,
                    patch.object(manager, "get_mac_address", side_effect=get_mac),
                    patch.object(
                        manager, "manage_modem", return_value=("admin", "secret")
                    ) as manage_modem,
                    self.assertRaises(SystemExit),
                ):
                    manager.main()

                self.assertEqual(checked_hosts, expected_hosts)
                self.assertEqual(manager.host, expected_hosts[-1])
                if mac_results[-1]:
                    self.assertEqual(manager.mac_address, mac_results[-1])
                    manage_modem.assert_called_once()
                    self.assertEqual(input_mock.call_count, 2)
                else:
                    manage_modem.assert_not_called()
                    self.assertEqual(input_mock.call_count, 1)

    def test_explicit_address_does_not_fall_back_to_defaults(self):
        manager = ModemManager()
        checked_hosts = []

        def get_mac():
            checked_hosts.append(manager.host)
            return None

        with (
            patch("main.os.path.exists", return_value=False),
            patch("builtins.input", return_value=" 10.0.0.1 ") as input_mock,
            patch.object(manager, "get_mac_address", side_effect=get_mac),
            patch.object(manager, "manage_modem") as manage_modem,
            self.assertRaises(SystemExit),
        ):
            manager.main()

        self.assertEqual(checked_hosts, ["10.0.0.1"])
        manage_modem.assert_not_called()
        input_mock.assert_called_once()

    def test_invalid_address_stops_before_detection(self):
        manager = ModemManager()
        with (
            patch("main.os.path.exists", return_value=False),
            patch("builtins.input", return_value="999.168.1.1"),
            patch.object(manager, "get_mac_address") as get_mac,
            self.assertRaises(ValueError),
        ):
            manager.main()
        get_mac.assert_not_called()

    def test_retrieval_failure_exits_without_prompting_to_save(self):
        for failed_result in (False, None, (None, None), ("", "")):
            with self.subTest(failed_result=failed_result):
                manager = ModemManager()
                with (
                    patch("main.os.path.exists", return_value=False),
                    patch.object(manager, "set_host", return_value="192.168.0.1"),
                    patch.object(
                        manager, "get_mac_address", return_value="FFFFFFFFFFFF"
                    ),
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
        input_mock.assert_called_once_with(
            "Do you want to save the configuration? [Y/Others] "
        )

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
            patch(
                "main.load_config",
                return_value={
                    "date": "2026-01-01 00:00:00",
                    "host": "192.168.0.1",
                    "mac_address": "AAAAAAAAAAAA",
                },
            ),
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
