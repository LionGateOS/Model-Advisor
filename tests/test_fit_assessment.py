import unittest

from liongateos_model_advisor.fit_assessment import assess_memory_budget
from liongateos_model_advisor.memory_estimate import ModelMemoryEstimate


class FitAssessmentTests(unittest.TestCase):
    def test_complete_estimate_can_prove_fit(self):
        estimate = ModelMemoryEstimate(
            model_id="example/model",
            artifact_id="example/artifact",
            context_length=8192,
            weight_bytes=8000,
            kv_cache_bytes=1000,
            kv_key_bytes_per_element=2,
            kv_value_bytes_per_element=2,
            recurrent_state_bytes=0,
            runtime_overhead_bytes=1000,
            known_minimum_bytes=10000,
            estimated_total_bytes=10000,
        )

        result = assess_memory_budget(
            estimate,
            budget_kind="gpu",
            target_id="gpu0",
            capacity_bytes=12000,
            available_bytes=11000,
        )

        self.assertEqual(result.capacity_status, "fits")
        self.assertEqual(result.availability_status, "fits")
        self.assertEqual(result.capacity_headroom_bytes, 2000)

    def test_complete_estimate_can_prove_no_fit(self):
        estimate = ModelMemoryEstimate(
            model_id="example/model",
            artifact_id="example/artifact",
            context_length=8192,
            weight_bytes=8000,
            kv_cache_bytes=1000,
            kv_key_bytes_per_element=2,
            kv_value_bytes_per_element=2,
            recurrent_state_bytes=0,
            runtime_overhead_bytes=1000,
            known_minimum_bytes=10000,
            estimated_total_bytes=10000,
        )

        result = assess_memory_budget(
            estimate,
            budget_kind="gpu",
            target_id="gpu0",
            capacity_bytes=9000,
            available_bytes=8000,
        )

        self.assertEqual(result.capacity_status, "does_not_fit")
        self.assertEqual(result.availability_status, "does_not_fit")

    def test_known_minimum_fit_remains_unknown_when_total_unknown(self):
        estimate = ModelMemoryEstimate(
            model_id="example/model",
            artifact_id="example/artifact",
            context_length=8192,
            known_minimum_bytes=9000,
        )

        result = assess_memory_budget(
            estimate,
            budget_kind="gpu",
            target_id="gpu0",
            capacity_bytes=12000,
            available_bytes=11000,
        )

        self.assertEqual(result.capacity_status, "unknown")
        self.assertEqual(result.availability_status, "unknown")

    def test_known_minimum_can_prove_no_fit(self):
        estimate = ModelMemoryEstimate(
            model_id="example/model",
            artifact_id="example/artifact",
            context_length=8192,
            known_minimum_bytes=13000,
        )

        result = assess_memory_budget(
            estimate,
            budget_kind="gpu",
            target_id="gpu0",
            capacity_bytes=12000,
            available_bytes=10000,
        )

        self.assertEqual(result.capacity_status, "does_not_fit")
        self.assertEqual(result.availability_status, "does_not_fit")


if __name__ == "__main__":
    unittest.main()


class HardwareFitBridgeTests(unittest.TestCase):
    def test_multiple_gpus_are_assessed_independently(self):
        from liongateos_model_advisor.hardware_profile import GPU, HardwareProfile
        from liongateos_model_advisor.fit_assessment import assess_gpu_budgets

        gib = 1024 ** 3
        estimate = ModelMemoryEstimate(
            model_id="example/model",
            artifact_id="example/artifact",
            context_length=8192,
            weight_bytes=25 * gib,
            kv_cache_bytes=0,
            kv_key_bytes_per_element=2,
            kv_value_bytes_per_element=2,
            recurrent_state_bytes=0,
            runtime_overhead_bytes=0,
            known_minimum_bytes=25 * gib,
            estimated_total_bytes=25 * gib,
        )
        hardware = HardwareProfile(
            gpus=(
                GPU(pci_address="0000:01:00.0", total_vram_bytes=24 * gib),
                GPU(pci_address="0000:02:00.0", total_vram_bytes=24 * gib),
            )
        )

        results = assess_gpu_budgets(estimate, hardware)

        self.assertEqual(len(results), 2)
        self.assertTrue(
            all(result.capacity_status == "does_not_fit" for result in results)
        )
