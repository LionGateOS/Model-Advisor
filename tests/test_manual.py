import unittest
from unittest.mock import patch

from liongateos_model_advisor.manual import enter_hardware_manually


class ManualEntryTests(unittest.TestCase):
    @patch("builtins.input")
    @patch("builtins.print")
    def test_manual_entry_builds_normalized_profile(self, _print, user_input):
        user_input.side_effect = iter(
            [
                "Linux",
                "Example 1",
                "linux",
                "x86_64",
                "AMD",
                "Example CPU",
                "8",
                "16",
                "64",
                "1",
                "NVIDIA",
                "Example GPU",
                "",
                "24",
            ]
        )

        profile = enter_hardware_manually()
        data = profile.to_dict()

        self.assertEqual(data["cpu"]["physical_cores"], 8)
        self.assertEqual(data["memory"]["total_bytes"], 64 * 1024**3)
        self.assertIsNone(data["memory"]["available_bytes"])
        self.assertEqual(data["gpus"][0]["total_vram_bytes"], 24 * 1024**3)
        self.assertIsNone(data["gpus"][0]["free_vram_bytes"])
        self.assertEqual(data["gpus"][0]["detection_sources"], ("manual",))

    @patch("builtins.input")
    @patch("builtins.print")
    def test_blank_manual_values_remain_unknown(self, _print, user_input):
        user_input.side_effect = iter(
            ["", "", "", "", "", "", "", "", "", ""]
        )

        profile = enter_hardware_manually()

        self.assertIsNone(profile.cpu.model)
        self.assertIsNone(profile.memory.total_bytes)
        self.assertIsNone(profile.memory.available_bytes)
        self.assertEqual(profile.gpus, ())


if __name__ == "__main__":
    unittest.main()
