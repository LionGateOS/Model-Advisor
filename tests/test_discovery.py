import unittest
from unittest.mock import patch

from liongateos_model_advisor.discovery import (
    _discover_pci_gpus,
    _enrich_nvidia,
)
from liongateos_model_advisor.hardware_profile import GPU


class DiscoveryTests(unittest.TestCase):
    @patch("liongateos_model_advisor.discovery._run")
    def test_discovers_nvidia_and_amd_from_lspci(self, run):
        run.return_value = (
            '0000:01:00.0 "VGA compatible controller [0300]" '
            '"NVIDIA Corporation [10de]" "GA102 [GeForce RTX 3090] [2204]"\n'
            '0000:7b:00.0 "VGA compatible controller [0300]" '
            '"Advanced Micro Devices, Inc. [AMD/ATI] [1002]" "Raphael [164e]"\n'
        )

        gpus = _discover_pci_gpus()

        self.assertEqual(len(gpus), 2)
        self.assertEqual(gpus[0].vendor, "NVIDIA")
        self.assertEqual(gpus[0].device_id, "2204")
        self.assertEqual(gpus[1].vendor, "AMD")
        self.assertIsNone(gpus[1].total_vram_bytes)

    @patch("liongateos_model_advisor.discovery._run")
    def test_nvidia_enrichment_matches_by_pci_address(self, run):
        run.return_value = (
            "NVIDIA GeForce RTX 3090, "
            "00000000:01:00.0, 24576, 580.173.02\n"
        )

        source = [
            GPU(
                vendor="NVIDIA",
                model="GA102 [GeForce RTX 3090]",
                pci_address="0000:01:00.0",
                vendor_id="10de",
                device_id="2204",
                detection_sources=("lspci",),
            )
        ]

        enriched = _enrich_nvidia(source)

        self.assertEqual(enriched[0].model, "NVIDIA GeForce RTX 3090")
        self.assertEqual(enriched[0].total_vram_bytes, 24576 * 1024 * 1024)
        self.assertEqual(
            enriched[0].detection_sources,
            ("lspci", "nvidia-smi"),
        )


if __name__ == "__main__":
    unittest.main()

class DiscoveryFallbackTests(unittest.TestCase):
    @patch("liongateos_model_advisor.discovery._run")
    def test_missing_lspci_returns_no_gpus_instead_of_failing(self, run):
        run.return_value = None

        gpus = _discover_pci_gpus()

        self.assertEqual(gpus, [])

    @patch("liongateos_model_advisor.discovery._run")
    def test_missing_nvidia_smi_preserves_pci_gpu_information(self, run):
        run.return_value = None
        source = [
            GPU(
                vendor="NVIDIA",
                model="GA102 [GeForce RTX 3090]",
                pci_address="0000:01:00.0",
                vendor_id="10de",
                device_id="2204",
                detection_sources=("lspci",),
            )
        ]

        enriched = _enrich_nvidia(source)

        self.assertEqual(enriched, source)
        self.assertIsNone(enriched[0].total_vram_bytes)
        self.assertEqual(enriched[0].detection_sources, ("lspci",))
