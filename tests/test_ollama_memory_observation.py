import unittest
from unittest.mock import patch

from liongateos_model_advisor.ollama_memory_observation import (
    observe_loaded_models,
)


class OllamaMemoryObservationTests(unittest.TestCase):

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_empty_models(self, request):
        request.return_value = {"models": []}
        self.assertEqual(
            observe_loaded_models(),
            {"status": "available", "models": []},
        )
        request.assert_called_once_with("/api/ps")

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_valid_memory_observation(self, request):
        request.return_value = {
            "models": [{
                "name": "example:latest",
                "size": 1000,
                "size_vram": 750,
                "model": "/private/model/path",
                "digest": "private-digest",
            }]
        }
        self.assertEqual(
            observe_loaded_models(),
            {
                "status": "available",
                "models": [{
                    "model_id": "ollama:example:latest",
                    "loaded_bytes": 1000,
                    "gpu_bytes": 750,
                }],
            },
        )

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_invalid_memory_values(self, request):
        request.return_value = {
            "models": [{
                "name": "example",
                "size": True,
                "size_vram": -1,
            }]
        }
        result = observe_loaded_models()
        self.assertIsNone(result["models"][0]["loaded_bytes"])
        self.assertIsNone(result["models"][0]["gpu_bytes"])

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_invalid_response(self, request):
        request.return_value = {"models": "invalid"}
        self.assertEqual(
            observe_loaded_models()["status"],
            "error",
        )

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_malformed_top_level_responses(self, request):
        for payload in (None, [], "invalid", 42):
            with self.subTest(payload=payload):
                request.return_value = payload
                self.assertEqual(
                    observe_loaded_models(),
                    {"status": "error", "models": []},
                )

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_unavailable_api(self, request):
        request.side_effect = OSError("unavailable")
        self.assertEqual(
            observe_loaded_models(),
            {"status": "unavailable", "models": []},
        )

    @patch("liongateos_model_advisor.ollama_memory_observation._request_json")
    def test_unexpected_fields_not_exposed(self, request):
        request.return_value = {
            "models": [{
                "name": "example",
                "size": 100,
                "size_vram": 50,
                "private_path": "/secret/path",
                "token": "secret-token",
            }]
        }
        result = str(observe_loaded_models())
        self.assertNotIn("/secret/path", result)
        self.assertNotIn("secret-token", result)


    def test_dashboard_filters_remote_memory_observations(self):
        from liongateos_model_advisor.dashboard import collect_dashboard_data
        from liongateos_model_advisor.model_profile import ModelProfile, ModelArtifact, ModelIdentity
        from liongateos_model_advisor.hardware_profile import HardwareProfile, CPU
        from liongateos_model_advisor.runtime_profile import RuntimeProfile
        from liongateos_model_advisor.compatibility_profile import CompatibilityProfile

        profile = ModelProfile(
            models=(
                ModelIdentity(model_id="ollama:local"),
                ModelIdentity(model_id="ollama:remote"),
            ),
            artifacts=(
                ModelArtifact(artifact_id="local", model_id="ollama:local", location="local"),
                ModelArtifact(artifact_id="remote", model_id="ollama:remote", location="remote"),
            ),
        )
        observations = {
            "status": "available",
            "models": [
                {"model_id": "ollama:local", "loaded_bytes": 100, "gpu_bytes": 80},
                {"model_id": "ollama:remote", "loaded_bytes": 200, "gpu_bytes": 150},
            ],
        }

        with (
            patch("liongateos_model_advisor.dashboard.discover_hardware",
                  return_value=HardwareProfile(cpu=CPU(model="test"))),
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
                  return_value=profile),
            patch("liongateos_model_advisor.dashboard.discover_huggingface_models",
                  return_value=ModelProfile()),
            patch("liongateos_model_advisor.dashboard.discover_openrouter_models",
                  return_value=ModelProfile()),
            patch("liongateos_model_advisor.dashboard.observe_loaded_models",
                  return_value=observations),
        ):
            result = collect_dashboard_data()

        self.assertEqual(
            [item["model_id"] for item in result["memory_observations"]["models"]],
            ["ollama:local"],
        )


if __name__ == "__main__":
    unittest.main()
