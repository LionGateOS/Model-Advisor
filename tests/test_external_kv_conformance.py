"""External KV-cache reference cases for existing hybrid calculations.

Reference: FitLLM fit-vectors-v1.json, three selected vectors.
Only calculation results are checked; no hardware-fit verdicts.
These tests use explicit architecture assumptions and do not establish
independent verification of upstream model configuration files.
"""

import unittest

from liongateos_model_advisor.memory_calculation import calculate_kv_cache_bytes
from liongateos_model_advisor.model_profile import ModelIdentity


class ExternalKVConformanceTests(unittest.TestCase):
    def test_reference_hybrid_kv_calculations(self):
        cases = (
            ("qwen27b-kv-131k-q8", 64, 4, 131072, 1.0, 4294967296),
            ("qwen38-27b-kv-full-f16", 64, 4, 262144, 2.0, 17179869184),
            ("agentworld-kv-10k", 40, 2, 10000, 2.0, 204800000),
        )

        for identifier, layers, heads, context, precision, expected in cases:
            with self.subTest(vector=identifier):
                model = ModelIdentity(
                    model_id=identifier,
                    block_count=layers,
                    attention_head_count_kv=heads,
                    attention_key_length=256,
                    attention_value_length=256,
                    full_attention_interval=4,
                )
                actual, reasons = calculate_kv_cache_bytes(
                    model,
                    context_length=context,
                    key_bytes_per_element=precision,
                    value_bytes_per_element=precision,
                )
                self.assertEqual(actual, expected)
                self.assertEqual(reasons, ())


    def test_reference_full_and_hybrid_attention_kv(self):
        # Architecture inputs are taken from FitLLM reference notes.
        # These tests do not independently verify upstream configs.
        cases = (
            ("hy3-kv-full-f16", 80, 8, 128, 262144, 85899345920),
            ("granite42-30b-kv-128k-f16", 64, 8, 128, 131072, 34359738368),
            ("minicpm5-2b-kv-128k-f16", 42, 2, 128, 131072, 5637144576),
            ("nex-n25-mini-kv-128k-f16", 40, 2, 256, 131072, 2684354560),
            ("nex-n25-pro-kv-128k-f16", 60, 2, 256, 131072, 4026531840),
        )
        for identifier, layers, heads, dimension, context, expected in cases:
            with self.subTest(vector=identifier):
                hybrid = identifier.startswith("nex-")
                model = ModelIdentity(
                    model_id=identifier,
                    block_count=layers,
                    attention_head_count_kv=heads,
                    attention_key_length=dimension,
                    attention_value_length=dimension,
                    full_attention_interval=4 if hybrid else 1,
                )
                actual, reasons = calculate_kv_cache_bytes(
                    model,
                    context_length=context,
                    key_bytes_per_element=2.0,
                    value_bytes_per_element=2.0,
                )
                self.assertEqual(actual, expected)
                self.assertEqual(reasons, ())


if __name__ == "__main__":
    unittest.main()
