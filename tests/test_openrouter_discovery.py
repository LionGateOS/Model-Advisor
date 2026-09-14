import unittest
from unittest.mock import patch

from liongateos_model_advisor.openrouter_discovery import discover_openrouter_models


class OpenRouterDiscoveryTests(unittest.TestCase):
    @patch("liongateos_model_advisor.openrouter_discovery._request_models")
    def test_linked_and_unlinked_offerings(self, request):
        request.return_value = [
            {
                "id": "example/linked",
                "hugging_face_id": "example/base",
                "context_length": 128000,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                },
                "supported_parameters": ["temperature", "tools"],
            },
            {"id": "example/provider-only"},
        ]

        profile = discover_openrouter_models(limit=2)

        self.assertEqual(profile.sources[0].status, "available")
        self.assertEqual(len(profile.models), 1)
        self.assertEqual(len(profile.offerings), 2)
        self.assertEqual(profile.models[0].model_id, "huggingface:example/base")
        self.assertEqual(profile.offerings[0].context_length, 128000)
        self.assertIsNone(profile.offerings[1].model_id)

    @patch("liongateos_model_advisor.openrouter_discovery._request_models")
    def test_unavailable_api_is_explicit(self, request):
        request.side_effect = OSError("offline")
        profile = discover_openrouter_models()
        self.assertEqual(profile.sources[0].status, "unavailable")

    def test_limit_is_bounded(self):
        with self.assertRaises(ValueError):
            discover_openrouter_models(limit=101)


if __name__ == "__main__":
    unittest.main()
