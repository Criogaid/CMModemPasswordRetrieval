import unittest
from unittest.mock import patch

from main import Credentials, main


class MainFlowTests(unittest.TestCase):
    def test_empty_address_tries_defaults_in_order_and_stops_on_success(self):
        cases = (
            (["AABBCCDDEEFF"], ["192.168.0.1"]),
            ([None, "AABBCCDDEEFF"], ["192.168.0.1", "192.168.1.1"]),
            ([None, None], ["192.168.0.1", "192.168.1.1"]),
        )
        for mac_results, expected_hosts in cases:
            with self.subTest(mac_results=mac_results):
                with (
                    patch("main.os.path.exists", return_value=False),
                    patch("builtins.input", side_effect=["", "n"]) as input_mock,
                    patch("main.get_mac_address", side_effect=mac_results) as get_mac,
                    patch(
                        "main.retrieve_credentials",
                        return_value=Credentials("admin", "secret"),
                    ) as retrieve,
                    self.assertRaises(SystemExit),
                ):
                    main()

                self.assertEqual(
                    [call.args[0] for call in get_mac.call_args_list], expected_hosts
                )
                if mac_results[-1]:
                    retrieve.assert_called_once_with(
                        expected_hosts[-1], mac_results[-1]
                    )
                    self.assertEqual(input_mock.call_count, 2)
                else:
                    retrieve.assert_not_called()
                    self.assertEqual(input_mock.call_count, 1)

    def test_explicit_address_does_not_fall_back_to_defaults(self):
        with (
            patch("main.os.path.exists", return_value=False),
            patch("builtins.input", return_value=" 10.0.0.1 ") as input_mock,
            patch("main.get_mac_address", return_value=None) as get_mac,
            patch("main.retrieve_credentials") as retrieve,
            self.assertRaises(SystemExit),
        ):
            main()

        get_mac.assert_called_once_with("10.0.0.1")
        retrieve.assert_not_called()
        input_mock.assert_called_once()

    def test_invalid_address_stops_before_detection(self):
        with (
            patch("main.os.path.exists", return_value=False),
            patch("builtins.input", return_value="999.168.1.1"),
            patch("main.get_mac_address") as get_mac,
            self.assertRaises(ValueError),
        ):
            main()
        get_mac.assert_not_called()

    def test_retrieval_failure_exits_without_prompting_to_save(self):
        for failed_result in (
            None,
            Credentials("", ""),
            Credentials("", "partial-password"),
            Credentials("partial-account", ""),
        ):
            with self.subTest(failed_result=failed_result):
                with (
                    patch("main.os.path.exists", return_value=False),
                    patch("main.prompt_host", return_value="192.168.0.1"),
                    patch("main.get_mac_address", return_value="FFFFFFFFFFFF"),
                    patch("main.retrieve_credentials", return_value=failed_result),
                    patch("builtins.input") as input_mock,
                ):
                    with self.assertRaises(SystemExit) as raised:
                        main()

                self.assertEqual(raised.exception.code, 0)
                input_mock.assert_not_called()

    def test_partial_password_is_displayed_without_prompting_to_save(self):
        with (
            patch("main.os.path.exists", return_value=False),
            patch("main.prompt_host", return_value="192.168.0.1"),
            patch("main.get_mac_address", return_value="FFFFFFFFFFFF"),
            patch(
                "main.retrieve_credentials",
                return_value=Credentials("", "retrieved-secret"),
            ),
            patch("main.logger.info") as info,
            patch("main.logger.warning") as warning,
            patch("builtins.input") as input_mock,
            self.assertRaises(SystemExit),
        ):
            main()

        messages = "\n".join(call.args[0] for call in info.call_args_list)
        self.assertIn("retrieved-secret", messages)
        self.assertNotIn("CMCCAdmin", messages)
        warning.assert_called()
        input_mock.assert_not_called()

    def test_success_still_prompts_to_save(self):
        with (
            patch("main.os.path.exists", return_value=False),
            patch("main.prompt_host", return_value="192.168.0.1"),
            patch("main.get_mac_address", return_value="FFFFFFFFFFFF"),
            patch(
                "main.retrieve_credentials",
                return_value=Credentials("admin", "password"),
            ),
            patch("builtins.input", return_value="n") as input_mock,
        ):
            with self.assertRaises(SystemExit) as raised:
                main()

        self.assertEqual(raised.exception.code, 0)
        input_mock.assert_called_once_with(
            "Do you want to save the configuration? [Y/Others] "
        )

    def test_missing_mac_exits_before_modem_management(self):
        with (
            patch("main.os.path.exists", return_value=False),
            patch("main.prompt_host", return_value="192.168.0.1"),
            patch("main.get_mac_address", return_value=None),
            patch("main.retrieve_credentials") as retrieve,
            patch("builtins.input") as input_mock,
        ):
            with self.assertRaises(SystemExit) as raised:
                main()

        self.assertEqual(raised.exception.code, 0)
        retrieve.assert_not_called()
        input_mock.assert_not_called()

    def test_declining_saved_config_saves_the_detected_endpoint(self):
        with (
            patch("main.os.path.exists", return_value=True),
            patch("main.load_config") as load,
            patch("builtins.input", side_effect=["n", "", "y"]),
            patch("main.get_mac_address", side_effect=[None, "AABBCCDDEEFF"]),
            patch(
                "main.retrieve_credentials",
                return_value=Credentials("admin", "password"),
            ) as retrieve,
            patch("main.save_config", return_value="saved") as save,
            self.assertRaises(SystemExit),
        ):
            main()

        load.assert_not_called()
        retrieve.assert_called_once_with("192.168.1.1", "AABBCCDDEEFF")
        save.assert_called_once()
        self.assertEqual(save.call_args.args[1:], ("192.168.1.1", "AABBCCDDEEFF"))

    def test_loaded_config_skips_network_validation(self):
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
            patch("main.get_mac_address") as get_mac_address,
            patch(
                "main.retrieve_credentials",
                return_value=Credentials("admin", "password"),
            ) as retrieve,
            patch("builtins.input", side_effect=["y", "n"]),
        ):
            with self.assertRaises(SystemExit) as raised:
                main()

        self.assertEqual(raised.exception.code, 0)
        retrieve.assert_called_once_with("192.168.0.1", "AAAAAAAAAAAA")
        get_mac_address.assert_not_called()


if __name__ == "__main__":
    unittest.main()
