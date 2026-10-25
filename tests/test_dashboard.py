import unittest
from unittest.mock import patch

from liongateos_model_advisor.compatibility_profile import (
    CompatibilityProfile,
    RuntimeCompatibility,
)
from liongateos_model_advisor.dashboard import collect_dashboard_data
from liongateos_model_advisor.hardware_profile import CPU, HardwareProfile
from liongateos_model_advisor.model_profile import (
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
    ModelSourceStatus,
)
from liongateos_model_advisor.runtime_profile import Runtime, RuntimeProfile


class DashboardDataTests(unittest.TestCase):
    @patch("liongateos_model_advisor.dashboard.discover_openrouter_models")
    @patch("liongateos_model_advisor.dashboard.discover_huggingface_models")
    @patch("liongateos_model_advisor.dashboard.discover_ollama_models")
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
        discover_models,
        discover_huggingface,
        discover_openrouter,
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

        discover_models.return_value = ModelProfile(
            models=(
                ModelIdentity(
                    model_id="ollama:example:latest",
                    parameter_count=7_000_000_000,
                ),
            ),
            artifacts=(
                ModelArtifact(
                    artifact_id="ollama:example:latest:artifact",
                    model_id="ollama:example:latest",
                    location="local",
                    format="gguf",
                    quantization="Q4_K_M",
                    size_bytes=4_000_000_000,
                ),
            ),
            sources=(
                ModelSourceStatus(
                    source="ollama-local-api",
                    status="available",
                ),
            ),
        )

        discover_huggingface.return_value = ModelProfile()
        discover_openrouter.return_value = ModelProfile()

        data = collect_dashboard_data(
            ["/private/example/llama.cpp/bin"]
        )
        self.assertNotIn("runtime_paths", data)

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
        self.assertEqual(
            data["models"]["models"][0]["model_id"],
            "ollama:example:latest",
        )
        self.assertEqual(
            data["models"]["artifacts"][0]["location"],
            "local",
        )
        self.assertEqual(
            data["models"]["sources"][0]["status"],
            "available",
        )
        self.assertEqual(
            [item["context_length"] for item in data["context_comparisons"][0]["options"]],
            [4096, 8192, 16384, 32768],
        )
        self.assertTrue(
            all(
                item["total_memory_status"] == "unknown"
                for item in data["context_comparisons"][0]["options"]
            )
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
        discover_models.assert_called_once_with()
        discover_huggingface.assert_called_once_with()
        discover_openrouter.assert_called_once_with()

    @patch("liongateos_model_advisor.dashboard.discover_openrouter_models")
    @patch("liongateos_model_advisor.dashboard.discover_huggingface_models")
    @patch("liongateos_model_advisor.dashboard.discover_ollama_models")
    @patch("liongateos_model_advisor.dashboard.assess_compatibility")
    @patch("liongateos_model_advisor.dashboard.collect_runtime_capability_evidence")
    @patch("liongateos_model_advisor.dashboard.discover_runtimes")
    @patch("liongateos_model_advisor.dashboard.discover_hardware")
    def test_context_comparison_excludes_remote_artifacts_and_preserves_unknowns(
        self,
        discover_hardware,
        discover_runtimes,
        collect_evidence,
        assess,
        discover_models,
        discover_huggingface,
        discover_openrouter,
    ):
        hardware = HardwareProfile()
        runtimes = RuntimeProfile()
        compatibility = CompatibilityProfile(
            hardware_schema_version="1",
            runtime_schema_version="1",
        )
        local = ModelIdentity(
            model_id="ollama:local",
            context_length=None,
        )
        remote = ModelIdentity(
            model_id="ollama:remote",
            context_length=32768,
        )

        discover_hardware.return_value = hardware
        discover_runtimes.return_value = runtimes
        collect_evidence.return_value = ()
        assess.return_value = compatibility
        discover_models.return_value = ModelProfile(
            models=(local, remote),
            artifacts=(
                ModelArtifact(
                    artifact_id="local-artifact",
                    model_id=local.model_id,
                    location="local",
                ),
                ModelArtifact(
                    artifact_id="remote-artifact",
                    model_id=remote.model_id,
                    location="remote",
                ),
            ),
        )
        discover_huggingface.return_value = ModelProfile()
        discover_openrouter.return_value = ModelProfile()

        data = collect_dashboard_data()

        self.assertEqual(
            [item["model_id"] for item in data["context_comparisons"]],
            ["ollama:local"],
        )
        self.assertTrue(
            all(
                option["context_status"] == "unknown"
                for option in data["context_comparisons"][0]["options"]
            )
        )
        self.assertTrue(
            all(
                option["kv_cache_bytes"] is None
                for option in data["context_comparisons"][0]["options"]
            )
        )



class DashboardFP16ScenarioTests(unittest.TestCase):
    def test_dashboard_explicitly_supplies_fp16_sizes(self):
        from pathlib import Path

        source = Path(
            "src/liongateos_model_advisor/dashboard.py"
        ).read_text()

        self.assertIn("key_bytes_per_element=2.0", source)
        self.assertIn("value_bytes_per_element=2.0", source)

    def test_dashboard_labels_assumption(self):
        from pathlib import Path

        script = Path(
            "src/liongateos_model_advisor/web/dashboard.js"
        ).read_text()

        self.assertIn("assumed FP16", script)
        self.assertIn("not a detected runtime setting", script)
        self.assertIn("KV cache (FP16 scenario)", script)

if __name__ == "__main__":
    unittest.main()
