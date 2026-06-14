import json
import os
import tempfile
import unittest

from main import is_yes_response, load_config, normalize_mac_address, save_config, validate_host


class MainHelperTests(unittest.TestCase):
    def test_is_yes_response_only_accepts_y(self):
        self.assertTrue(is_yes_response("Y"))
        self.assertTrue(is_yes_response(" y "))
        self.assertFalse(is_yes_response(""))
        self.assertFalse(is_yes_response("yes"))
        self.assertFalse(is_yes_response("n"))

    def test_normalize_mac_address_accepts_common_formats(self):
        self.assertEqual(normalize_mac_address("ff-ff-ff-ff-ff-ff"), "FFFFFFFFFFFF")
        self.assertEqual(normalize_mac_address("ff:ff:ff:ff:ff:ff"), "FFFFFFFFFFFF")
        self.assertEqual(normalize_mac_address("ffffffffffff"), "FFFFFFFFFFFF")

    def test_normalize_mac_address_rejects_invalid_values(self):
        self.assertIsNone(normalize_mac_address(""))
        self.assertIsNone(normalize_mac_address("ff-ff"))
        self.assertIsNone(normalize_mac_address("zz-zz-zz-zz-zz-zz"))

    def test_validate_host(self):
        self.assertTrue(validate_host("192.168.0.1"))
        self.assertFalse(validate_host(""))
        self.assertFalse(validate_host("999.168.0.1"))
        self.assertFalse(validate_host("not-an-ip"))

    def test_load_config_normalizes_valid_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "CMCCModelConfig.json")
            with open(config_file, "w", encoding="utf-8") as file:
                json.dump({
                    "date": "2026-01-01 00:00:00",
                    "host": "192.168.0.1",
                    "mac_address": "ff-ff-ff-ff-ff-ff",
                }, file)

            config = load_config(config_file)

            self.assertEqual(config["host"], "192.168.0.1")
            self.assertEqual(config["mac_address"], "FFFFFFFFFFFF")

    def test_load_config_rejects_invalid_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "CMCCModelConfig.json")
            with open(config_file, "w", encoding="utf-8") as file:
                json.dump({"host": "999.168.0.1", "mac_address": "ff-ff"}, file)

            with self.assertRaises(ValueError):
                load_config(config_file)

    def test_save_config_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "CMCCModelConfig.json")

            with self.assertRaises(ValueError):
                save_config(config_file, "192.168.0.1", None)


if __name__ == "__main__":
    unittest.main()
