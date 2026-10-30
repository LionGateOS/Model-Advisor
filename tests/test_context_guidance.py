import unittest

from liongateos_model_advisor.context_guidance import compare_context_options
from liongateos_model_advisor.hardware_profile import GPU, HardwareProfile
from liongateos_model_advisor.model_profile import ModelArtifact, ModelIdentity


class ContextGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.model = ModelIdentity(
            model_id="example/context",
            context_length=16384,
            block_count=4,
            attention_head_count_kv=2,
            attention_key_length=64,
            attention_value_length=64,
            full_attention_interval=1,
        )
        self.artifact = ModelArtifact(
            artifact_id="example/context:q8",
            model_id=self.model.model_id,
            location="local",
            size_bytes=8_000_000_000,
        )
        self.hardware = HardwareProfile(
            gpus=(
                GPU(total_vram_bytes=1_000_000, free_vram_bytes=800_000),
                GPU(total_vram_bytes=2_000_000, free_vram_bytes=1_500_000),
            )
        )

    def test_context_scales_kv_and_never_proves_total_fit(self):
        options = compare_context_options(
            self.model, self.artifact, self.hardware,
            context_lengths=(4096, 8192),
            key_bytes_per_element=2,
            value_bytes_per_element=2,
        )
        self.assertEqual(len(options), 2)
        self.assertEqual(
            options[1].kv_cache_bytes,
            options[0].kv_cache_bytes * 2,
        )
        self.assertTrue(
            all(option.total_memory_status == "unknown" for option in options)
        )
        self.assertTrue(
            all(
                assessment["capacity_status"] != "fits"
                for option in options
                for assessment in option.gpu_assessments
            )
        )

    def test_context_above_reported_limit_is_flagged(self):
        options = compare_context_options(
            self.model, self.artifact, self.hardware,
            context_lengths=(16384, 32768),
            key_bytes_per_element=2,
            value_bytes_per_element=2,
        )
        self.assertEqual(options[0].context_status, "within_reported_limit")
        self.assertEqual(options[1].context_status, "exceeds_reported_limit")

    def test_gpu_assessments_remain_independent(self):
        options = compare_context_options(
            self.model, self.artifact, self.hardware,
            context_lengths=(4096,),
            key_bytes_per_element=2,
            value_bytes_per_element=2,
        )
        assessments = options[0].gpu_assessments
        self.assertEqual(len(assessments), 2)
        self.assertEqual(
            [assessment["target_id"] for assessment in assessments],
            ["gpu:0", "gpu:1"],
        )
        self.assertEqual(
            [assessment["capacity_bytes"] for assessment in assessments],
            [1_000_000, 2_000_000],
        )

    def test_missing_kv_precision_remains_unknown(self):
        option = compare_context_options(
            self.model, self.artifact, self.hardware,
            context_lengths=(4096,),
        )[0]
        self.assertIsNone(option.kv_cache_bytes)
        self.assertEqual(option.total_memory_status, "unknown")

    def test_missing_topology_remains_unknown(self):
        model = ModelIdentity(
            model_id="example/context",
            context_length=16384,
            block_count=4,
            attention_head_count_kv=2,
            attention_key_length=64,
            attention_value_length=64,
        )
        option = compare_context_options(
            model, self.artifact, self.hardware,
            context_lengths=(4096,),
            key_bytes_per_element=2,
            value_bytes_per_element=2,
        )[0]
        self.assertIsNone(option.kv_cache_bytes)

    def test_invalid_context_lengths_rejected(self):
        for lengths in ((), (0,), (-1,), (True,), (4096.5,)):
            with self.subTest(lengths=lengths):
                with self.assertRaises(ValueError):
                    compare_context_options(
                        self.model, self.artifact, self.hardware,
                        context_lengths=lengths,
                    )
