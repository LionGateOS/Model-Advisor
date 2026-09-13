import unittest

from liongateos_model_advisor.compatibility import (
    RuntimeCapabilityEvidence,
    assess_compatibility,
)
from liongateos_model_advisor.hardware_profile import GPU, HardwareProfile
from liongateos_model_advisor.runtime_profile import Runtime, RuntimeProfile


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.hardware = HardwareProfile(
            gpus=(
                GPU(
                    vendor="NVIDIA",
                    model="NVIDIA GeForce RTX 3090",
                    total_vram_bytes=24 * 1024**3,
                ),
            )
        )

    def test_positive_backend_evidence_marks_runtime_compatible(self):
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="llama.cpp", available=True),
            )
        )

        profile = assess_compatibility(
            self.hardware,
            runtimes,
            (
                RuntimeCapabilityEvidence(
                    runtime_name="llama.cpp",
                    gpu_backend="CUDA",
                    gpu_vendors=("NVIDIA",),
                    gpu_models=("NVIDIA GeForce RTX 3090",),
                    source="llama-list-devices",
                ),
            ),
        )

        result = profile.runtimes[0]

        self.assertEqual(result.status, "compatible")
        self.assertIn(
            "runtime-reports-cuda-gpu-support",
            result.reasons,
        )
        self.assertIn("llama-list-devices", result.evidence_sources)

    def test_observed_active_gpu_execution_marks_runtime_compatible(self):
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="ollama", available=True),
            )
        )

        profile = assess_compatibility(
            self.hardware,
            runtimes,
            (
                RuntimeCapabilityEvidence(
                    runtime_name="ollama",
                    active_gpu_execution=True,
                    source="ollama-ps",
                ),
            ),
        )

        result = profile.runtimes[0]

        self.assertEqual(result.status, "compatible")
        self.assertEqual(
            result.reasons,
            ("active-gpu-execution-observed",),
        )
        self.assertIn("ollama-ps", result.evidence_sources)

    def test_installed_without_backend_evidence_remains_unknown(self):
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="ollama", available=True),
            )
        )

        profile = assess_compatibility(self.hardware, runtimes)

        self.assertEqual(profile.runtimes[0].status, "unknown")
        self.assertEqual(
            profile.runtimes[0].reasons,
            ("backend-capability-not-proven",),
        )

    def test_backend_for_different_vendor_does_not_claim_compatibility(self):
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="example-runtime", available=True),
            )
        )

        profile = assess_compatibility(
            self.hardware,
            runtimes,
            (
                RuntimeCapabilityEvidence(
                    runtime_name="example-runtime",
                    gpu_backend="ROCm",
                    gpu_vendors=("AMD",),
                    source="example-probe",
                ),
            ),
        )

        self.assertEqual(profile.runtimes[0].status, "unknown")

    def test_unavailable_runtime_remains_unavailable_even_with_evidence(self):
        runtimes = RuntimeProfile(
            runtimes=(
                Runtime(name="vllm", available=False),
            )
        )

        profile = assess_compatibility(
            self.hardware,
            runtimes,
            (
                RuntimeCapabilityEvidence(
                    runtime_name="vllm",
                    gpu_backend="CUDA",
                    gpu_vendors=("NVIDIA",),
                    source="vllm-collect-env",
                ),
            ),
        )

        self.assertEqual(profile.runtimes[0].status, "unavailable")


if __name__ == "__main__":
    unittest.main()
