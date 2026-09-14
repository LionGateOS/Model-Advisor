import unittest

from liongateos_model_advisor.compatibility import RuntimeCapabilityEvidence
from liongateos_model_advisor.execution_fit import classify_gpu_execution
from liongateos_model_advisor.hardware_profile import GPU, HardwareProfile
from liongateos_model_advisor.memory_estimate import MemoryBudgetAssessment


class ExecutionFitTests(unittest.TestCase):
    def test_multi_gpu_support_creates_candidate_not_proven_fit(self):
        hardware = HardwareProfile(
            gpus=(
                GPU(total_vram_bytes=24 * 1024**3),
                GPU(total_vram_bytes=24 * 1024**3),
            )
        )
        assessments = (
            MemoryBudgetAssessment(
                model_id="example/model",
                artifact_id="example/artifact",
                budget_kind="gpu",
                target_id="gpu:0",
                capacity_status="does_not_fit",
            ),
            MemoryBudgetAssessment(
                model_id="example/model",
                artifact_id="example/artifact",
                budget_kind="gpu",
                target_id="gpu:1",
                capacity_status="does_not_fit",
            ),
        )
        capability = RuntimeCapabilityEvidence(
            runtime_name="llama.cpp",
            supports_multi_device=True,
            supports_gpu_offload=True,
        )

        result = classify_gpu_execution(
            assessments,
            hardware,
            capability,
        )

        self.assertEqual(result.single_gpu_status, "does_not_fit")
        self.assertEqual(result.multi_gpu_status, "candidate")
        self.assertIn("multi-gpu-fit-not-proven", result.reasons)

    def test_single_gpu_fit_does_not_require_multi_gpu(self):
        hardware = HardwareProfile(
            gpus=(GPU(total_vram_bytes=24 * 1024**3),)
        )
        assessments = (
            MemoryBudgetAssessment(
                model_id="example/model",
                artifact_id="example/artifact",
                budget_kind="gpu",
                target_id="gpu:0",
                capacity_status="fits",
            ),
        )

        result = classify_gpu_execution(
            assessments,
            hardware,
            None,
        )

        self.assertEqual(result.single_gpu_status, "fits")
        self.assertEqual(result.multi_gpu_status, "not_needed")


if __name__ == "__main__":
    unittest.main()
