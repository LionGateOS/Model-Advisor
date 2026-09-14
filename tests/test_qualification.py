import unittest

from liongateos_model_advisor.compatibility_profile import RuntimeCompatibility
from liongateos_model_advisor.execution_fit import GPUExecutionClassification
from liongateos_model_advisor.qualification import qualify_gpu_model


class QualificationTests(unittest.TestCase):
    def qualify(self, runtime_status, single, multi):
        return qualify_gpu_model(
            model_id="model:test",
            artifact_id="artifact:test",
            runtime=RuntimeCompatibility(
                runtime_name="llama.cpp",
                status=runtime_status,
                reasons=("runtime-evidence",),
                evidence_sources=("test-source",),
            ),
            execution=GPUExecutionClassification(
                single_gpu_status=single,
                multi_gpu_status=multi,
                reasons=("execution-evidence",),
            ),
        )

    def test_single_gpu_fit_is_qualified(self):
        result = self.qualify("compatible", "fits", "not_needed")
        self.assertEqual(result.status, "qualified")
        self.assertEqual(result.execution_path, "single_gpu")

    def test_multi_gpu_candidate_is_not_promoted_to_qualified(self):
        result = self.qualify("compatible", "does_not_fit", "candidate")
        self.assertEqual(result.status, "candidate")
        self.assertEqual(result.execution_path, "multi_gpu")

    def test_unusable_runtime_is_not_qualified(self):
        for status in ("incompatible", "unavailable"):
            with self.subTest(status=status):
                result = self.qualify(status, "fits", "not_needed")
                self.assertEqual(result.status, "not_qualified")
                self.assertEqual(result.execution_path, "none")

    def test_no_available_gpu_path_is_not_qualified(self):
        result = self.qualify("compatible", "does_not_fit", "unavailable")
        self.assertEqual(result.status, "not_qualified")
        self.assertEqual(result.execution_path, "none")

    def test_incomplete_evidence_remains_unknown(self):
        result = self.qualify("unknown", "fits", "not_needed")
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.execution_path, "unknown")
        self.assertEqual(result.evidence_sources, ("test-source",))


if __name__ == "__main__":
    unittest.main()

class QualificationIntegrationTests(unittest.TestCase):
    def test_memory_fit_flows_into_qualification_with_provenance(self):
        from liongateos_model_advisor.hardware_profile import GPU, HardwareProfile
        from liongateos_model_advisor.memory_estimate import ModelMemoryEstimate
        from liongateos_model_advisor.qualification import qualify_gpu_model_from_evidence

        estimate = ModelMemoryEstimate(
            model_id="model:test",
            artifact_id="artifact:test",
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
        hardware = HardwareProfile(
            gpus=(GPU(total_vram_bytes=12000, free_vram_bytes=11000),)
        )
        runtime = RuntimeCompatibility(
            runtime_name="llama.cpp",
            status="compatible",
            evidence_sources=("runtime-proof",),
        )

        result = qualify_gpu_model_from_evidence(
            estimate=estimate,
            hardware=hardware,
            runtime=runtime,
            capability=None,
        )

        self.assertEqual(result.status, "qualified")
        self.assertEqual(result.execution_path, "single_gpu")
        self.assertIn("runtime-proof", result.evidence_sources)
        self.assertIn("hardware-profile", result.evidence_sources)
