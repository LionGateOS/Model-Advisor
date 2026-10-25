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


if __name__ == "__main__":
    unittest.main()
