import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from liongateos_model_advisor.cli import main
from liongateos_model_advisor.hardware_profile import CPU, HardwareProfile


class CLITests(unittest.TestCase):
    @patch("liongateos_model_advisor.cli.discover_hardware")
    def test_cli_outputs_normalized_json_profile(self, discover):
        discover.return_value = HardwareProfile(
            cpu=CPU(
                vendor="AuthenticAMD",
                model="Example CPU",
                architecture="x86_64",
                physical_cores=8,
                logical_cpus=16,
            )
        )

        output = io.StringIO()
        with redirect_stdout(output):
            result = main([])

        data = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(data["schema_version"], "1")
        self.assertEqual(data["cpu"]["model"], "Example CPU")
        self.assertEqual(data["cpu"]["logical_cpus"], 16)

    @patch("liongateos_model_advisor.cli.enter_hardware_manually")
    def test_manual_flag_uses_manual_profile(self, manual):
        manual.return_value = HardwareProfile(
            cpu=CPU(model="Manual CPU")
        )

        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["--manual"])

        data = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(data["cpu"]["model"], "Manual CPU")


if __name__ == "__main__":
    unittest.main()
