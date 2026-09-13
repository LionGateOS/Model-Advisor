import unittest
from unittest.mock import patch

from liongateos_model_advisor.compatibility_profile import (
    CompatibilityProfile,
    RuntimeCompatibility,
)
from liongateos_model_advisor.dashboard import collect_dashboard_data
from liongateos_model_advisor.hardware_profile import CPU, HardwareProfile
from liongateos_model_advisor.runtime_profile import Runtime, RuntimeProfile


class DashboardDataTests(unittest.TestCase):
    @patch("liongateos_model_advisor.dashboard.assess_compatibility")
    @patch(
        "liongateos_model_advisor.dashboard.collect_runtime_capability_evidence"
    )
    @patch("liongateos_model_advisor.dashboard.discover_runtimes")
    @patch("liongateos_model_advisor.dashboard.discover_hardware")
    def test_dashboard_data_reuses_existing_profiles(
        self,
        discover_hardware,
        discover_runtimes,
        collect_evidence,
        assess,
    ):
        hardware = HardwareProfile(
            cpu=CPU(model="Example CPU"),
        )
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(
                    name="llama.cpp",
                    available=True,
                    version="example-version",
                ),
            )
        )
        compatibility = CompatibilityProfile(
            hardware_schema_version="1",
            runtime_schema_version="1",
            runtimes=(
                RuntimeCompatibility(
                    runtime_name="llama.cpp",
                    status="compatible",
                    reasons=("Positive runtime evidence.",),
                    evidence_sources=("example-probe",),
                ),
            ),
        )

        discover_hardware.return_value = hardware
        discover_runtimes.return_value = runtimes
        collect_evidence.return_value = ("example-evidence",)
        assess.return_value = compatibility

        data = collect_dashboard_data(
            ["/private/example/llama.cpp/bin"]
        )

        self.assertEqual(
            data["hardware"]["cpu"]["model"],
            "Example CPU",
        )
        self.assertEqual(
            data["runtimes"]["runtimes"][0]["name"],
            "llama.cpp",
        )
        self.assertEqual(
            data["compatibility"]["runtimes"][0]["status"],
            "compatible",
        )

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
            ("example-evidence",),
        )


if __name__ == "__main__":
    unittest.main()
