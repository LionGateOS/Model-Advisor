import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from liongateos_model_advisor.catalog_discovery import (
    HUGGINGFACE_MAX_DETAIL_LOOKUPS,
    HUGGINGFACE_MAX_LIMIT,
    _build_huggingface_url,
    discover_huggingface_models,
)
from liongateos_model_advisor.model_sources import (
    profile_from_huggingface_model_info,
)


class HuggingFaceCatalogDiscoveryTests(unittest.TestCase):
    def test_builds_bounded_huggingface_query(self):
        url = _build_huggingface_url(
            search="Qwen instruct",
            sort="downloads",
            limit=25,
            pipeline_tag="text-generation",
            num_parameters="min:6B,max:32B",
        )

        parsed = urlsplit(url)
        params = parse_qs(parsed.query)

        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "huggingface.co")
        self.assertEqual(parsed.path, "/api/models")
        self.assertEqual(params["search"], ["Qwen instruct"])
        self.assertEqual(params["sort"], ["downloads"])
        self.assertEqual(params["direction"], ["-1"])
        self.assertEqual(params["limit"], ["25"])
        self.assertEqual(params["pipeline_tag"], ["text-generation"])
        self.assertEqual(
            params["num_parameters"],
            ["min:6B,max:32B"],
        )
        self.assertEqual(params["full"], ["true"])
        self.assertEqual(params["cardData"], ["true"])

    def test_rejects_unbounded_limit(self):
        with self.assertRaises(ValueError):
            _build_huggingface_url(
                search=None,
                sort="trending_score",
                limit=HUGGINGFACE_MAX_LIMIT + 1,
                pipeline_tag=None,
                num_parameters=None,
            )

    def test_rejects_unbounded_detail_limit(self):
        with self.assertRaises(ValueError):
            discover_huggingface_models(
                detail_limit=HUGGINGFACE_MAX_DETAIL_LOOKUPS + 1,
            )

    def test_rejects_unknown_sort(self):
        with self.assertRaises(ValueError):
            _build_huggingface_url(
                search=None,
                sort="not-a-real-sort",
                limit=20,
                pipeline_tag=None,
                num_parameters=None,
            )

    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_detail"
    )
    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_list"
    )
    def test_discovers_with_bounded_detail_enrichment(
        self,
        list_request,
        detail_request,
    ):
        list_request.return_value = [
            {
                "id": "example/Model-A",
                "pipeline_tag": "text-generation",
                "tags": ["license:apache-2.0"],
            },
            {
                "id": "example/Model-B",
                "pipeline_tag": "text-generation",
            },
        ]

        detail_request.side_effect = [
            {
                "id": "example/Model-A",
                "pipeline_tag": "text-generation",
                "cardData": {
                    "license": "apache-2.0",
                },
                "safetensors": {
                    "total": 7_000_000_000,
                },
                "config": {
                    "model_type": "example",
                    "max_position_embeddings": 131_072,
                },
            },
            {
                "id": "example/Model-B",
                "pipeline_tag": "text-generation",
                "safetensors": {
                    "parameters": {
                        "BF16": 3_000_000_000,
                        "F32": 100_000_000,
                    },
                },
            },
        ]

        profile = discover_huggingface_models(
            search="example",
            limit=10,
            detail_limit=2,
        )

        self.assertEqual(profile.sources[0].status, "available")
        self.assertIsNone(profile.sources[0].reason)
        self.assertEqual(
            [model.model_id for model in profile.models],
            [
                "huggingface:example/Model-A",
                "huggingface:example/Model-B",
            ],
        )

        first = profile.models[0]
        second = profile.models[1]

        self.assertEqual(first.parameter_count, 7_000_000_000)
        self.assertEqual(first.architecture, "example")
        self.assertEqual(first.context_length, 131_072)
        self.assertEqual(first.license, "apache-2.0")
        self.assertEqual(second.parameter_count, 3_100_000_000)
        self.assertEqual(len(profile.artifacts), 2)
        self.assertEqual(detail_request.call_count, 2)

        list_request.assert_called_once_with(
            search="example",
            sort="trending_score",
            limit=10,
            pipeline_tag=None,
            num_parameters=None,
        )

    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_list"
    )
    def test_unavailable_api_remains_explicit(self, request):
        request.side_effect = OSError("network unavailable")

        profile = discover_huggingface_models()

        self.assertEqual(profile.models, ())
        self.assertEqual(profile.artifacts, ())
        self.assertEqual(profile.sources[0].status, "unavailable")
        self.assertEqual(profile.sources[0].reason, "api-unavailable")

    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_detail"
    )
    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_list"
    )
    def test_bad_record_does_not_discard_good_records(
        self,
        list_request,
        detail_request,
    ):
        list_request.return_value = [
            {"not-an-id": "bad"},
            {
                "id": "example/good-model",
                "pipeline_tag": "text-generation",
            },
        ]
        detail_request.return_value = {
            "id": "example/good-model",
            "pipeline_tag": "text-generation",
        }

        profile = discover_huggingface_models()

        self.assertEqual(
            [model.model_id for model in profile.models],
            ["huggingface:example/good-model"],
        )
        self.assertEqual(profile.sources[0].status, "partial")
        self.assertEqual(
            profile.sources[0].reason,
            "one-or-more-model-records-unusable",
        )

    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_detail"
    )
    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_list"
    )
    def test_detail_failure_falls_back_to_listing(
        self,
        list_request,
        detail_request,
    ):
        list_request.return_value = [
            {
                "id": "example/fallback",
                "pipeline_tag": "text-generation",
                "tags": ["license:apache-2.0"],
            }
        ]
        detail_request.side_effect = OSError("detail unavailable")

        profile = discover_huggingface_models()

        self.assertEqual(len(profile.models), 1)
        self.assertEqual(
            profile.models[0].model_id,
            "huggingface:example/fallback",
        )
        self.assertEqual(
            profile.models[0].tasks,
            ("text-generation",),
        )
        self.assertEqual(
            profile.models[0].license,
            "apache-2.0",
        )
        self.assertEqual(profile.sources[0].status, "partial")
        self.assertEqual(
            profile.sources[0].reason,
            "one-or-more-model-details-unavailable",
        )

    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_detail"
    )
    @patch(
        "liongateos_model_advisor.catalog_discovery."
        "_request_huggingface_model_list"
    )
    def test_duplicate_model_ids_are_deduplicated(
        self,
        list_request,
        detail_request,
    ):
        list_request.return_value = [
            {"id": "example/duplicate"},
            {"id": "example/duplicate"},
        ]
        detail_request.return_value = {
            "id": "example/duplicate",
        }

        profile = discover_huggingface_models()

        self.assertEqual(len(profile.models), 1)
        self.assertEqual(
            profile.models[0].model_id,
            "huggingface:example/duplicate",
        )
        self.assertEqual(detail_request.call_count, 1)

    def test_huggingface_gguf_metadata_preserves_reported_geometry(self):
        profile = profile_from_huggingface_model_info(
            {
                "id": "example/model-gguf",
                "pipeline_tag": "text-generation",
                "cardData": {
                    "license": "apache-2.0",
                },
                "gguf": {
                    "architecture": "examplemoe",
                    "context_length": 262_144,
                    "total": 30_532_122_624,
                    "totalFileSize": 17_310_784_672,
                },
                "siblings": [
                    {"rfilename": "example-Q4_K_M.gguf"},
                    {"rfilename": "example-Q8_0.gguf"},
                ],
            }
        )

        self.assertEqual(len(profile.models), 1)
        self.assertEqual(profile.models[0].architecture, "examplemoe")
        self.assertEqual(profile.models[0].context_length, 262_144)

        # GGUF repo-level totals are not promoted to exact model parameters
        # or concrete artifact sizes without stronger per-artifact evidence.
        self.assertIsNone(profile.models[0].parameter_count)
        self.assertEqual(profile.artifacts, ())


if __name__ == "__main__":
    unittest.main()
