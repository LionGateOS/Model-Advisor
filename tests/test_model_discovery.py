import json
import unittest
from unittest.mock import call, patch

from liongateos_model_advisor.model_discovery import (
    discover_ollama_models,
)


class OllamaModelDiscoveryTests(unittest.TestCase):
    @patch(
        "liongateos_model_advisor.model_discovery._request_json"
    )
    def test_discovers_and_normalizes_local_ollama_model(self, request):
        request.side_effect = (
            {
                "models": [
                    {
                        "name": "example:latest",
                        "model": "example:latest",
                        "digest": "sha256:abc123",
                        "size": 2_800_000_000,
                    }
                ]
            },
            {
                "details": {
                    "format": "gguf",
                    "family": "example",
                    "parameter_size": "4.3B",
                    "quantization_level": "Q4_K_M",
                },
                "model_info": {
                    "general.architecture": "example",
                    "general.parameter_count": 4_299_915_632,
                    "example.context_length": 131_072,
                },
                "capabilities": ["completion", "tools"],
            },
        )

        profile = discover_ollama_models()

        self.assertEqual(len(profile.models), 1)
        self.assertEqual(len(profile.artifacts), 1)
        self.assertEqual(profile.sources[0].status, "available")
        self.assertIsNone(profile.sources[0].reason)

        model = profile.models[0]
        artifact = profile.artifacts[0]

        self.assertEqual(model.model_id, "ollama:example:latest")
        self.assertEqual(model.parameter_count, 4_299_915_632)
        self.assertEqual(model.context_length, 131_072)
        self.assertEqual(artifact.digest, "sha256:abc123")
        self.assertEqual(artifact.location, "local")
        self.assertEqual(artifact.size_bytes, 2_800_000_000)

        encoded = json.dumps(profile.to_dict())

        self.assertEqual(
            request.call_args_list,
            [
                call("/api/tags"),
                call("/api/show", {"model": "example:latest"}),
            ],
        )

    @patch(
        "liongateos_model_advisor.model_discovery._request_json"
    )
    def test_remote_registration_is_not_treated_as_local_weights(
        self,
        request,
    ):
        request.side_effect = (
            {
                "models": [
                    {
                        "name": "cloud-example:cloud",
                        "digest": "sha256:remote123",
                        "size": 308,
                        "remote_host": "private.example.invalid",
                        "remote_model": "private/model",
                    }
                ]
            },
            {
                "details": {
                    "parameter_size": "2.81T",
                    "quantization_level": "MXFP4",
                },
                "model_info": {
                    "general.architecture": "example",
                    "general.parameter_count": 2_812_000_000_000,
                    "example.context_length": 1_048_576,
                },
                "capabilities": ["completion"],
            },
        )

        profile = discover_ollama_models()

        self.assertEqual(len(profile.models), 1)
        self.assertEqual(len(profile.artifacts), 1)

        artifact = profile.artifacts[0]

        self.assertEqual(artifact.location, "remote")
        self.assertIsNone(artifact.size_bytes)
        self.assertEqual(artifact.quantization, "MXFP4")

        encoded = json.dumps(profile.to_dict())

        self.assertNotIn("private.example.invalid", encoded)
        self.assertNotIn("private/model", encoded)

    @patch(
        "liongateos_model_advisor.model_discovery._request_json"
    )
    def test_unavailable_ollama_api_returns_empty_profile(self, request):
        request.side_effect = OSError("connection refused")

        profile = discover_ollama_models()

        self.assertEqual(profile.models, ())
        self.assertEqual(profile.artifacts, ())
        self.assertEqual(profile.sources[0].status, "unavailable")
        self.assertEqual(profile.sources[0].reason, "api-unavailable")

    @patch(
        "liongateos_model_advisor.model_discovery._request_json"
    )
    def test_invalid_tags_shape_returns_empty_profile(self, request):
        request.return_value = {
            "models": "not-a-list",
        }

        profile = discover_ollama_models()

        self.assertEqual(profile.models, ())
        self.assertEqual(profile.artifacts, ())
        self.assertEqual(profile.sources[0].status, "error")
        self.assertEqual(
            profile.sources[0].reason,
            "invalid-model-list-response",
        )

    @patch(
        "liongateos_model_advisor.model_discovery._request_json"
    )
    def test_failed_show_skips_only_that_model(self, request):
        def fake_request(path, payload=None):
            if path == "/api/tags":
                return {
                    "models": [
                        {"name": "bad:latest"},
                        {"name": "good:latest"},
                    ]
                }

            if payload == {"model": "bad:latest"}:
                raise OSError("show failed")

            return {
                "details": {
                    "format": "gguf",
                    "parameter_size": "7B",
                },
                "model_info": {
                    "general.parameter_count": 7_000_000_000,
                },
            }

        request.side_effect = fake_request

        profile = discover_ollama_models()

        self.assertEqual(
            [model.model_id for model in profile.models],
            ["ollama:good:latest"],
        )
        self.assertEqual(profile.sources[0].status, "partial")
        self.assertEqual(
            profile.sources[0].reason,
            "one-or-more-model-details-unavailable",
        )


if __name__ == "__main__":
    unittest.main()
