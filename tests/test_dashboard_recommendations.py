"""Dashboard workload recommendation integration regressions."""

import unittest
from pathlib import Path
from unittest.mock import patch

from liongateos_model_advisor.compatibility_profile import CompatibilityProfile
from liongateos_model_advisor.dashboard import collect_dashboard_data
from liongateos_model_advisor.hardware_profile import HardwareProfile
from liongateos_model_advisor.model_profile import (
    MetadataEvidence,
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
)
from liongateos_model_advisor.runtime_profile import RuntimeProfile


class DashboardRecommendationTests(unittest.TestCase):
    def collect(self, *, reported=True, remote=False):
        model = ModelIdentity(
            model_id="ollama:example",
            tasks=("code-generation",),
            evidence=(
                MetadataEvidence(
                    field="tasks",
                    source="test:tasks",
                    kind="reported",
                ),
            ) if reported else (),
        )
        artifacts = [
            ModelArtifact(
                artifact_id="local-artifact",
                model_id=model.model_id,
                location="local",
            ),
        ]

        if remote:
            artifacts = [
                ModelArtifact(
                    artifact_id="remote-artifact",
                    model_id=model.model_id,
                    location="remote",
                ),
            ]

        with (
            patch("liongateos_model_advisor.dashboard.discover_hardware",
                  return_value=HardwareProfile()),
            patch("liongateos_model_advisor.dashboard.discover_runtimes",
                  return_value=RuntimeProfile()),
            patch("liongateos_model_advisor.dashboard.collect_runtime_capability_evidence",
                  return_value=()),
            patch("liongateos_model_advisor.dashboard.assess_compatibility",
                  return_value=CompatibilityProfile(
                      hardware_schema_version="1",
                      runtime_schema_version="1",
                  )),
            patch("liongateos_model_advisor.dashboard.discover_ollama_models",
                  return_value=ModelProfile(
                      models=(model,),
                      artifacts=tuple(artifacts),
                  )),
            patch("liongateos_model_advisor.dashboard.observe_loaded_models",
                  return_value={"status": "available", "models": []}),
            patch("liongateos_model_advisor.dashboard.discover_huggingface_models",
                  return_value=ModelProfile()),
            patch("liongateos_model_advisor.dashboard.discover_openrouter_models",
                  return_value=ModelProfile()),
        ):
            return collect_dashboard_data()

    def test_three_workloads_returned(self):
        data = self.collect()
        results = data["workload_recommendations"]
        self.assertEqual(
            [item["workload"] for item in results],
            ["coding", "general_chat", "reasoning"],
        )

    def test_unknown_hardware_never_supported(self):
        data = self.collect()
        results = data["workload_recommendations"]
        self.assertTrue(all(
            item["status"] != "supported_candidate"
            for item in results
        ))

    def test_missing_reported_metadata_is_unknown(self):
        data = self.collect(reported=False)
        self.assertTrue(all(
            item["status"] == "workload_unknown"
            for item in data["workload_recommendations"]
        ))

    def test_remote_artifacts_excluded(self):
        data = self.collect(remote=True)
        self.assertEqual(data["workload_recommendations"], [])

    def test_frontend_has_recommendation_rendering(self):
        script = Path(
            "src/liongateos_model_advisor/web/dashboard.js"
        ).read_text()
        self.assertIn("Workload recommendations", script)
        self.assertIn("workload_recommendations", script)
        self.assertIn("Hardware verification needed", script)


if __name__ == "__main__":
    unittest.main()
