import unittest

from liongateos_model_advisor.model_sources import (
    profile_from_gguf_metadata,
    profile_from_huggingface_model_info,
    profile_from_ollama_show,
)


class ModelSourceTests(unittest.TestCase):
    def test_huggingface_uses_exact_safetensors_total(self):
        profile = profile_from_huggingface_model_info(
            {
                "id": "example/model",
                "pipeline_tag": "text-generation",
                "tags": ["license:apache-2.0"],
                "safetensors": {
                    "total": 7_241_748_480,
                },
            }
        )

        model = profile.models[0]
        artifact = profile.artifacts[0]

        self.assertEqual(
            model.model_id,
            "huggingface:example/model",
        )
        self.assertEqual(model.parameter_count, 7_241_748_480)
        self.assertEqual(model.tasks, ("text-generation",))
        self.assertEqual(model.license, "apache-2.0")
        self.assertEqual(artifact.format, "safetensors")

    def test_huggingface_can_derive_total_from_dtype_counts(self):
        profile = profile_from_huggingface_model_info(
            {
                "id": "example/model",
                "safetensors": {
                    "parameters": {
                        "BF16": 7_000_000_000,
                        "F32": 100,
                    }
                },
            }
        )

        model = profile.models[0]

        self.assertEqual(model.parameter_count, 7_000_000_100)

        parameter_evidence = [
            item
            for item in model.evidence
            if item.field == "parameter_count"
        ]

        self.assertEqual(len(parameter_evidence), 1)
        self.assertEqual(parameter_evidence[0].kind, "derived")

    def test_huggingface_does_not_infer_parameters_from_name(self):
        profile = profile_from_huggingface_model_info(
            {
                "id": "example/model-27B",
                "tags": [],
            }
        )

        self.assertIsNone(profile.models[0].parameter_count)

    def test_ollama_keeps_size_label_separate_from_exact_count(self):
        profile = profile_from_ollama_show(
            "example:latest",
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
                    "example.block_count": 3,
                    "example.embedding_length": 4096,
                    "example.attention.head_count": 32,
                    "example.attention.head_count_kv": [8, 8, 4],
                    "example.attention.key_length": 128,
                    "example.attention.value_length": 128,
                    "example.nextn_predict_layers": 1,
                    "example.full_attention_interval": 4,
                    "example.attention.recurrent_layers": [
                        True,
                        True,
                        False,
                    ],
                    "example.attention.sliding_window": 4096,
                    "example.ssm.conv_kernel": 4,
                    "example.ssm.group_count": 8,
                    "example.ssm.inner_size": 2048,
                    "example.ssm.state_size": 128,
                    "example.ssm.time_step_rank": 32,
                },
                "capabilities": ["completion", "tools"],
            },
            size_bytes=2_800_000_000,
            digest="sha256:abc123",
            artifact_location="local",
        )

        model = profile.models[0]
        artifact = profile.artifacts[0]

        self.assertEqual(model.parameter_size_label, "4.3B")
        self.assertEqual(model.parameter_count, 4_299_915_632)
        self.assertEqual(model.context_length, 131_072)
        self.assertEqual(model.block_count, 3)
        self.assertEqual(model.embedding_length, 4096)
        self.assertEqual(model.attention_head_count, 32)
        self.assertEqual(model.attention_head_count_kv, (8, 8, 4))
        self.assertEqual(model.attention_key_length, 128)
        self.assertEqual(model.attention_value_length, 128)
        self.assertEqual(model.nextn_predict_layers, 1)
        self.assertEqual(model.full_attention_interval, 4)
        self.assertEqual(
            model.attention_recurrent_layers,
            (True, True, False),
        )
        self.assertEqual(model.attention_sliding_window, 4096)
        self.assertEqual(model.ssm_conv_kernel, 4)
        self.assertEqual(model.ssm_group_count, 8)
        self.assertEqual(model.ssm_inner_size, 2048)
        self.assertEqual(model.ssm_state_size, 128)
        self.assertEqual(model.ssm_time_step_rank, 32)
        self.assertEqual(
            model.capabilities,
            ("completion", "tools"),
        )
        self.assertEqual(artifact.digest, "sha256:abc123")
        self.assertEqual(artifact.location, "local")
        self.assertEqual(artifact.format, "gguf")
        self.assertEqual(artifact.quantization, "Q4_K_M")
        self.assertEqual(artifact.size_bytes, 2_800_000_000)

    def test_ollama_does_not_promote_approximate_label(self):
        profile = profile_from_ollama_show(
            "example:latest",
            {
                "details": {
                    "parameter_size": "27B",
                    "format": "gguf",
                },
                "model_info": {},
            },
        )

        model = profile.models[0]

        self.assertEqual(model.parameter_size_label, "27B")
        self.assertIsNone(model.parameter_count)

    def test_gguf_uses_standardized_metadata_without_guessing(self):
        profile = profile_from_gguf_metadata(
            model_id="example/model",
            artifact_id="example/model:q8_0",
            metadata={
                "general.name": "Example Model",
                "general.architecture": "example",
                "general.parameter_count": 27_123_456_789,
                "general.size_label": "27B",
                "general.license": "Apache-2.0",
                "example.context_length": 65_536,
                "example.block_count": 48,
                "example.embedding_length": 5120,
                "example.attention.head_count": 40,
                "example.attention.head_count_kv": 8,
                "example.attention.key_length": 128,
                "example.attention.value_length": 128,
                "example.nextn_predict_layers": 1,
                "example.full_attention_interval": 4,
                "example.attention.sliding_window": 2048,
                "example.ssm.conv_kernel": 4,
                "example.ssm.group_count": 8,
                "example.ssm.inner_size": 2048,
                "example.ssm.state_size": 128,
                "example.ssm.time_step_rank": 32,
                "general.file_type": 7,
            },
            size_bytes=28_000_000_000,
        )

        model = profile.models[0]
        artifact = profile.artifacts[0]

        self.assertEqual(model.display_name, "Example Model")
        self.assertEqual(model.architecture, "example")
        self.assertEqual(model.parameter_count, 27_123_456_789)
        self.assertEqual(model.parameter_size_label, "27B")
        self.assertEqual(model.context_length, 65_536)
        self.assertEqual(model.block_count, 48)
        self.assertEqual(model.embedding_length, 5120)
        self.assertEqual(model.attention_head_count, 40)
        self.assertEqual(model.attention_head_count_kv, 8)
        self.assertEqual(model.attention_key_length, 128)
        self.assertEqual(model.attention_value_length, 128)
        self.assertEqual(model.nextn_predict_layers, 1)
        self.assertEqual(model.full_attention_interval, 4)
        self.assertEqual(model.attention_sliding_window, 2048)
        self.assertEqual(model.ssm_conv_kernel, 4)
        self.assertEqual(model.ssm_group_count, 8)
        self.assertEqual(model.ssm_inner_size, 2048)
        self.assertEqual(model.ssm_state_size, 128)
        self.assertEqual(model.ssm_time_step_rank, 32)
        self.assertEqual(model.license, "Apache-2.0")
        self.assertEqual(artifact.format, "gguf")
        self.assertIsNone(artifact.quantization)
        self.assertEqual(artifact.size_bytes, 28_000_000_000)


if __name__ == "__main__":
    unittest.main()
