import json
import unittest

from liongateos_model_advisor.memory_estimate import (
    MEMORY_ESTIMATE_SCHEMA_VERSION,
    EstimateEvidence,
    MemoryBudgetAssessment,
    ModelMemoryEstimate,
)


class ModelMemoryEstimateTests(unittest.TestCase):
    def test_memory_components_serialize_without_hiding_unknowns(self):
        estimate = ModelMemoryEstimate(
            model_id="ollama:example",
            artifact_id="ollama:example:artifact",
            context_length=8192,
            weight_bytes=8_000_000_000,
            kv_cache_bytes=1_000_000_000,
            kv_key_bytes_per_element=2.0,
            kv_value_bytes_per_element=2.0,
            recurrent_state_bytes=None,
            runtime_overhead_bytes=None,
            known_minimum_bytes=9_000_000_000,
            estimated_total_bytes=None,
            reasons=("runtime-overhead-unknown",),
            evidence=(
                EstimateEvidence(
                    field="weight_bytes",
                    source="ollama:model-list-size",
                    kind="reported",
                ),
                EstimateEvidence(
                    field="kv_cache_bytes",
                    source="model-geometry",
                    kind="derived",
                ),
            ),
        )

        data = json.loads(json.dumps(estimate.to_dict()))

        self.assertEqual(data["weight_bytes"], 8_000_000_000)
        self.assertEqual(data["kv_cache_bytes"], 1_000_000_000)
        self.assertEqual(data["kv_key_bytes_per_element"], 2.0)
        self.assertEqual(data["kv_value_bytes_per_element"], 2.0)
        self.assertIsNone(data["recurrent_state_bytes"])
        self.assertIsNone(data["runtime_overhead_bytes"])
        self.assertEqual(data["known_minimum_bytes"], 9_000_000_000)
        self.assertIsNone(data["estimated_total_bytes"])
        self.assertEqual(
            data["reasons"],
            ["runtime-overhead-unknown"],
        )

    def test_total_requires_all_components(self):
        with self.assertRaises(ValueError):
            ModelMemoryEstimate(
                model_id="example/model",
                artifact_id="example/artifact",
                context_length=4096,
                weight_bytes=4_000,
                kv_cache_bytes=1_000,
                kv_key_bytes_per_element=2.0,
                kv_value_bytes_per_element=2.0,
                recurrent_state_bytes=0,
                runtime_overhead_bytes=None,
                known_minimum_bytes=5_000,
                estimated_total_bytes=5_500,
            )

    def test_known_minimum_cannot_hide_known_components(self):
        with self.assertRaises(ValueError):
            ModelMemoryEstimate(
                model_id="example/model",
                artifact_id="example/artifact",
                context_length=4096,
                weight_bytes=4_000,
                kv_cache_bytes=1_000,
                kv_key_bytes_per_element=2.0,
                kv_value_bytes_per_element=2.0,
                recurrent_state_bytes=0,
                known_minimum_bytes=4_500,
            )


    def test_known_kv_requires_explicit_precision(self):
        with self.assertRaises(ValueError):
            ModelMemoryEstimate(
                model_id="example/model",
                artifact_id="example/artifact",
                context_length=4096,
                weight_bytes=4_000,
                kv_cache_bytes=1_000,
                known_minimum_bytes=5_000,
            )

    def test_kv_key_and_value_precision_are_paired(self):
        with self.assertRaises(ValueError):
            ModelMemoryEstimate(
                model_id="example/model",
                artifact_id="example/artifact",
                context_length=4096,
                kv_key_bytes_per_element=2.0,
            )

    def test_recurrent_state_contributes_to_known_minimum(self):
        with self.assertRaises(ValueError):
            ModelMemoryEstimate(
                model_id="example/hybrid",
                artifact_id="example/hybrid:artifact",
                context_length=8192,
                weight_bytes=8_000,
                recurrent_state_bytes=2_000,
                known_minimum_bytes=9_000,
            )


class MemoryBudgetAssessmentTests(unittest.TestCase):
    def test_capacity_and_current_availability_are_separate(self):
        assessment = MemoryBudgetAssessment(
            model_id="ollama:example",
            artifact_id="ollama:example:artifact",
            budget_kind="gpu",
            target_id="0000:01:00.0",
            capacity_bytes=24_000,
            available_bytes=10_000,
            capacity_headroom_bytes=4_000,
            available_headroom_bytes=-10_000,
            capacity_status="fits",
            availability_status="does_not_fit",
            reasons=(
                "fits-empty-device-capacity",
                "does-not-fit-currently-available-memory",
            ),
        )

        data = assessment.to_dict()

        self.assertEqual(data["capacity_status"], "fits")
        self.assertEqual(
            data["availability_status"],
            "does_not_fit",
        )
        self.assertEqual(data["capacity_headroom_bytes"], 4_000)
        self.assertEqual(data["available_headroom_bytes"], -10_000)

    def test_unknown_status_is_explicit(self):
        assessment = MemoryBudgetAssessment(
            model_id="example/model",
            artifact_id="example/artifact",
            budget_kind="system-memory",
            target_id="system",
        )

        self.assertEqual(assessment.capacity_status, "unknown")
        self.assertEqual(assessment.availability_status, "unknown")

    def test_available_memory_cannot_exceed_capacity(self):
        with self.assertRaises(ValueError):
            MemoryBudgetAssessment(
                model_id="example/model",
                artifact_id="example/artifact",
                budget_kind="gpu",
                target_id="gpu0",
                capacity_bytes=10_000,
                available_bytes=11_000,
            )

    def test_invalid_budget_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            MemoryBudgetAssessment(
                model_id="example/model",
                artifact_id="example/artifact",
                budget_kind="pooled-gpus",
                target_id="all",
            )

    def test_schema_version_is_stable(self):
        self.assertEqual(MEMORY_ESTIMATE_SCHEMA_VERSION, "1")


if __name__ == "__main__":
    unittest.main()
