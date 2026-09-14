import unittest

from liongateos_model_advisor.memory_calculation import (
    calculate_kv_cache_bytes,
    estimate_model_memory,
)
from liongateos_model_advisor.model_profile import (
    ModelArtifact,
    ModelIdentity,
)


class KVCacheCalculationTests(unittest.TestCase):
    def test_qwen35_interval_excludes_recurrent_and_nextn_layers(self):
        model = ModelIdentity(
            model_id="example/qwen35",
            context_length=262144,
            block_count=65,
            attention_head_count_kv=4,
            attention_key_length=256,
            attention_value_length=256,
            nextn_predict_layers=1,
            full_attention_interval=4,
            ssm_state_size=128,
        )

        result, reasons = calculate_kv_cache_bytes(
            model,
            context_length=8192,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        # 64 trunk layers / interval 4 = 16 full-attention layers.
        # 8192 * 16 * 4 * ((256 * 2) + (256 * 2))
        self.assertEqual(result, 536_870_912)
        self.assertEqual(reasons, ())

    def test_explicit_recurrent_map_selects_only_attention_layers(self):
        model = ModelIdentity(
            model_id="example/hybrid",
            block_count=4,
            attention_head_count_kv=(8, 4, 8, 4),
            attention_key_length=64,
            attention_value_length=64,
            attention_recurrent_layers=(
                True,
                False,
                True,
                False,
            ),
        )

        result, reasons = calculate_kv_cache_bytes(
            model,
            context_length=4096,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        # Only layers 1 and 3 are full attention: 4 + 4 KV heads.
        self.assertEqual(result, 8_388_608)
        self.assertEqual(reasons, ())

    def test_missing_topology_remains_unknown(self):
        model = ModelIdentity(
            model_id="example/unknown-topology",
            block_count=32,
            attention_head_count_kv=8,
            attention_key_length=128,
            attention_value_length=128,
        )

        result, reasons = calculate_kv_cache_bytes(
            model,
            context_length=4096,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        self.assertIsNone(result)
        self.assertEqual(
            reasons,
            ("attention-layer-topology-unknown",),
        )

    def test_sliding_window_without_layer_pattern_remains_unknown(self):
        model = ModelIdentity(
            model_id="example/sliding",
            block_count=32,
            attention_head_count_kv=8,
            attention_key_length=128,
            attention_value_length=128,
            attention_sliding_window=4096,
        )

        result, reasons = calculate_kv_cache_bytes(
            model,
            context_length=8192,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        self.assertIsNone(result)
        self.assertEqual(
            reasons,
            ("sliding-window-layer-pattern-unsupported",),
        )

    def test_missing_kv_geometry_remains_unknown(self):
        model = ModelIdentity(
            model_id="example/missing-kv",
            block_count=32,
            full_attention_interval=4,
        )

        result, reasons = calculate_kv_cache_bytes(
            model,
            context_length=4096,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        self.assertIsNone(result)
        self.assertEqual(reasons, ("kv-head-count-unknown",))


class ModelMemoryCalculationTests(unittest.TestCase):
    def test_artifact_size_is_not_promoted_to_weight_memory(self):
        model = ModelIdentity(
            model_id="example/model",
            block_count=4,
            attention_head_count_kv=2,
            attention_key_length=64,
            attention_value_length=64,
            full_attention_interval=1,
        )
        artifact = ModelArtifact(
            artifact_id="example/model:q8",
            model_id=model.model_id,
            location="local",
            format="gguf",
            size_bytes=8_000_000_000,
        )

        estimate = estimate_model_memory(
            model,
            artifact,
            context_length=4096,
            key_bytes_per_element=2.0,
            value_bytes_per_element=2.0,
        )

        self.assertIsNone(estimate.weight_bytes)
        self.assertIsNotNone(estimate.kv_cache_bytes)
        self.assertEqual(
            estimate.known_minimum_bytes,
            estimate.kv_cache_bytes,
        )
        self.assertIn(
            "artifact-size-is-storage-not-resident-weight-proof",
            estimate.reasons,
        )
        self.assertIn(
            "runtime-overhead-unknown",
            estimate.reasons,
        )
        self.assertIsNone(estimate.estimated_total_bytes)

    def test_missing_precision_keeps_kv_unknown(self):
        model = ModelIdentity(
            model_id="example/model",
            block_count=4,
            attention_head_count_kv=2,
            attention_key_length=64,
            attention_value_length=64,
            full_attention_interval=1,
        )
        artifact = ModelArtifact(
            artifact_id="example/model:q8",
            model_id=model.model_id,
            location="local",
        )

        estimate = estimate_model_memory(
            model,
            artifact,
            context_length=4096,
        )

        self.assertIsNone(estimate.kv_cache_bytes)
        self.assertIsNone(estimate.known_minimum_bytes)
        self.assertIn(
            "kv-element-size-unknown",
            estimate.reasons,
        )

    def test_artifact_must_belong_to_model(self):
        model = ModelIdentity(model_id="example/model")
        artifact = ModelArtifact(
            artifact_id="other/artifact",
            model_id="other/model",
        )

        with self.assertRaises(ValueError):
            estimate_model_memory(
                model,
                artifact,
                context_length=4096,
            )


if __name__ == "__main__":
    unittest.main()
