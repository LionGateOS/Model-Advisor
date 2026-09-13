import json
import unittest

from liongateos_model_advisor.hardware_profile import (
    CPU,
    GPU,
    HardwareProfile,
    Memory,
    OperatingSystem,
    SCHEMA_VERSION,
)


class HardwareProfileTests(unittest.TestCase):
    def test_profile_serializes_to_json(self):
        profile = HardwareProfile(
            os=OperatingSystem(
                name="Pop!_OS",
                version="24.04 LTS",
                identifier="pop",
                architecture="x86_64",
            ),
            cpu=CPU(
                vendor="AuthenticAMD",
                model="AMD Ryzen 7 7800X3D 8-Core Processor",
                architecture="x86_64",
                physical_cores=8,
                logical_cpus=16,
            ),
            memory=Memory(total_bytes=64892248 * 1024),
            gpus=(
                GPU(
                    vendor="NVIDIA",
                    model="NVIDIA GeForce RTX 3090",
                    pci_address="0000:01:00.0",
                    vendor_id="10de",
                    device_id="2204",
                    total_vram_bytes=24576 * 1024 * 1024,
                    driver_version="580.173.02",
                    detection_sources=("lspci", "nvidia-smi"),
                ),
            ),
        )

        encoded = json.dumps(profile.to_dict())
        decoded = json.loads(encoded)

        self.assertEqual(decoded["schema_version"], SCHEMA_VERSION)
        self.assertEqual(decoded["cpu"]["physical_cores"], 8)
        self.assertEqual(decoded["gpus"][0]["vendor_id"], "10de")
        self.assertEqual(
            decoded["gpus"][0]["detection_sources"],
            ["lspci", "nvidia-smi"],
        )

    def test_unknown_values_remain_unknown(self):
        profile = HardwareProfile(
            gpus=(
                GPU(
                    vendor="AMD",
                    model="Raphael",
                    pci_address="0000:7b:00.0",
                    total_vram_bytes=None,
                    detection_sources=("lspci",),
                ),
            )
        )

        data = profile.to_dict()

        self.assertIsNone(data["gpus"][0]["total_vram_bytes"])
        self.assertIsNone(data["cpu"]["model"])


if __name__ == "__main__":
    unittest.main()
