import unittest
from unittest.mock import patch

from liongateos_model_advisor.capability_discovery import (
    probe_llama_cpp,
    probe_ollama,
    probe_vllm,
)


class CapabilityDiscoveryTests(unittest.TestCase):
    @patch(
        "liongateos_model_advisor.capability_discovery._find_llama_executables"
    )
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_llama_cpp_reports_cuda_devices(self, run_probe, find_executables):
        find_executables.return_value = (
            {"llama-cli": "/example/llama-cli"},
            ("custom-path",),
        )
        run_probe.return_value = (
            "Available devices:\n"
            "  CUDA0: NVIDIA GeForce RTX 3090 Ti (24112 MiB, 9000 MiB free)\n"
            "  CUDA1: NVIDIA GeForce RTX 3090 (24124 MiB, 10000 MiB free)\n"
        )

        evidence = probe_llama_cpp()

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.gpu_backend, "CUDA")
        self.assertEqual(evidence.gpu_vendors, ("NVIDIA",))
        self.assertEqual(
            evidence.gpu_models,
            (
                "NVIDIA GeForce RTX 3090 Ti",
                "NVIDIA GeForce RTX 3090",
            ),
        )
        self.assertEqual(evidence.source, "llama-list-devices")

    @patch(
        "liongateos_model_advisor.capability_discovery._find_llama_executables"
    )
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_llama_cpp_reports_multi_gpu_features(self, run_probe, find_executables):
        find_executables.return_value = (
            {"llama-cli": "/example/llama-cli"},
            ("custom-path",),
        )
        run_probe.side_effect = [
            "CUDA0: NVIDIA GeForce RTX 3090 Ti\nCUDA1: NVIDIA GeForce RTX 3090\n",
            "--device <dev1,dev2>\n"
            "--gpu-layers N\n"
            "--split-mode {none,layer,row,tensor}\n"
            "--tensor-split N0,N1\n"
            "--fit [on|off]\n",
        ]

        evidence = probe_llama_cpp()

        self.assertTrue(evidence.supports_multi_device)
        self.assertTrue(evidence.supports_gpu_offload)
        self.assertEqual(
            evidence.supported_split_modes,
            ("none", "layer", "row", "tensor"),
        )
        self.assertTrue(evidence.supports_auto_fit)
        self.assertEqual(evidence.feature_source, "llama-help")

    @patch("liongateos_model_advisor.capability_discovery.shutil.which")
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_vllm_reports_cuda_environment(self, run_probe, which):
        which.return_value = "/example/vllm"
        run_probe.return_value = (
            "Is CUDA available            : True\n"
            "GPU 0: NVIDIA GeForce RTX 3090\n"
            "GPU 1: NVIDIA GeForce RTX 3090 Ti\n"
            "vLLM Version                 : 0.19.0\n"
        )

        evidence = probe_vllm()

        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.gpu_backend, "CUDA")
        self.assertEqual(evidence.gpu_vendors, ("NVIDIA",))
        self.assertEqual(evidence.source, "vllm-collect-env")

    @patch("liongateos_model_advisor.capability_discovery.shutil.which")
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_ollama_running_on_gpu_is_positive_evidence(self, run_probe, which):
        which.return_value = "/usr/local/bin/ollama"
        run_probe.return_value = (
            "NAME ID SIZE PROCESSOR CONTEXT UNTIL\n"
            "example abc 28 GB 100% GPU 262144 Forever\n"
        )

        evidence = probe_ollama()

        self.assertIsNotNone(evidence)
        self.assertTrue(evidence.active_gpu_execution)
        self.assertEqual(evidence.source, "ollama-ps")

    @patch("liongateos_model_advisor.capability_discovery.shutil.which")
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_ollama_without_gpu_execution_returns_no_positive_evidence(
        self,
        run_probe,
        which,
    ):
        which.return_value = "/usr/local/bin/ollama"
        run_probe.return_value = "NAME ID SIZE PROCESSOR CONTEXT UNTIL\n"

        self.assertIsNone(probe_ollama())

    @patch("liongateos_model_advisor.capability_discovery.shutil.which")
    @patch("liongateos_model_advisor.capability_discovery._run_probe")
    def test_failed_vllm_probe_returns_no_evidence(self, run_probe, which):
        which.return_value = "/example/vllm"
        run_probe.return_value = None

        self.assertIsNone(probe_vllm())


if __name__ == "__main__":
    unittest.main()
