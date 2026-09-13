"""Interactive manual hardware entry for LionGateOS Model Advisor."""

from __future__ import annotations

from .hardware_profile import CPU, GPU, HardwareProfile, Memory, OperatingSystem


def _text(prompt: str) -> str | None:
    value = input(prompt).strip()
    return value or None


def _integer(prompt: str) -> int | None:
    value = input(prompt).strip()
    if not value:
        return None
    number = int(value)
    if number < 0:
        raise ValueError("numeric values cannot be negative")
    return number


def _gib_to_bytes(prompt: str) -> int | None:
    value = input(prompt).strip()
    if not value:
        return None
    gib = float(value)
    if gib < 0:
        raise ValueError("memory values cannot be negative")
    return int(gib * 1024**3)


def enter_hardware_manually() -> HardwareProfile:
    print("Manual hardware entry — press Enter when a value is unknown.")

    os_info = OperatingSystem(
        name=_text("Operating system name: "),
        version=_text("Operating system version: "),
        identifier=_text("Operating system identifier (optional): "),
        architecture=_text("Architecture (for example x86_64 or arm64): "),
    )

    cpu = CPU(
        vendor=_text("CPU vendor: "),
        model=_text("CPU model: "),
        architecture=os_info.architecture,
        physical_cores=_integer("Physical CPU cores: "),
        logical_cpus=_integer("Logical CPUs/threads: "),
    )

    memory = Memory(
        total_bytes=_gib_to_bytes("System RAM in GiB: "),
    )

    gpu_count = _integer("Number of GPUs/accelerators: ") or 0
    gpus: list[GPU] = []

    for index in range(gpu_count):
        print(f"GPU {index + 1}:")
        gpus.append(
            GPU(
                vendor=_text("  Vendor: "),
                model=_text("  Model: "),
                pci_address=_text("  PCI address (optional): "),
                total_vram_bytes=_gib_to_bytes("  VRAM in GiB: "),
                detection_sources=("manual",),
            )
        )

    return HardwareProfile(
        os=os_info,
        cpu=cpu,
        memory=memory,
        gpus=tuple(gpus),
    )
