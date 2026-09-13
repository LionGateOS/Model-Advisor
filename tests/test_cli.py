import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from liongateos_model_advisor.cli import main
from liongateos_model_advisor.hardware_profile import CPU, HardwareProfile
from liongateos_model_advisor.runtime_profile import Runtime, RuntimeProfile


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

    @patch("liongateos_model_advisor.cli.discover_runtimes")
    def test_runtime_command_outputs_runtime_profile(self, discover):
        discover.return_value = RuntimeProfile(
            runtimes=(
                Runtime(
                    name="ollama",
                    available=True,
                    version="0.22.1",
                    executables=("ollama",),
                    discovery_sources=("path",),
                ),
            )
        )

        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["runtimes"])

        data = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(data["runtimes"][0]["name"], "ollama")
        self.assertEqual(data["runtimes"][0]["version"], "0.22.1")
        discover.assert_called_once_with([])

    @patch("liongateos_model_advisor.cli.discover_runtimes")
    def test_runtime_paths_are_forwarded_without_being_printed(self, discover):
        discover.return_value = RuntimeProfile()

        output = io.StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "runtimes",
                    "--runtime-path",
                    "/private/example/llama.cpp/bin",
                ]
            )

        self.assertEqual(result, 0)
        self.assertNotIn("/private/example", output.getvalue())
        discover.assert_called_once_with(
            ["/private/example/llama.cpp/bin"]
        )


    @patch("liongateos_model_advisor.cli.assess_compatibility")
    @patch(
        "liongateos_model_advisor.cli.collect_runtime_capability_evidence"
    )
    @patch("liongateos_model_advisor.cli.discover_runtimes")
    @patch("liongateos_model_advisor.cli.discover_hardware")
    def test_compatibility_command_combines_discovery_and_evidence(
        self,
        discover_hardware,
        discover_runtimes,
        collect_evidence,
        assess,
    ):
        hardware = HardwareProfile(
            cpu=CPU(model="Example CPU")
        )
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="llama.cpp", available=True),
            )
        )
        compatibility = RuntimeProfile()

        discover_hardware.return_value = hardware
        discover_runtimes.return_value = runtimes
        collect_evidence.return_value = ()
        assess.return_value = compatibility

        output = io.StringIO()
        with redirect_stdout(output):
            result = main(
                [
                    "compatibility",
                    "--runtime-path",
                    "/private/example/llama.cpp/bin",
                ]
            )

        self.assertEqual(result, 0)
        discover_hardware.assert_called_once_with()
        discover_runtimes.assert_called_once_with(
            ["/private/example/llama.cpp/bin"]
        )
        collect_evidence.assert_called_once_with(
            runtimes,
            ["/private/example/llama.cpp/bin"],
        )
        assess.assert_called_once_with(
            hardware,
            runtimes,
            (),
        )
        self.assertNotIn("/private/example", output.getvalue())


if __name__ == "__main__":
    unittest.main()
