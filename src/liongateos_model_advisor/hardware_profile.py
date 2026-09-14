"""Normalized public hardware profile used by LionGateOS Model Advisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class OperatingSystem:
    name: str | None = None
    version: str | None = None
    identifier: str | None = None
    architecture: str | None = None


@dataclass(frozen=True)
class CPU:
    vendor: str | None = None
    model: str | None = None
    architecture: str | None = None
    physical_cores: int | None = None
    logical_cpus: int | None = None


@dataclass(frozen=True)
class Memory:
    total_bytes: int | None = None
    available_bytes: int | None = None


@dataclass(frozen=True)
class GPU:
    vendor: str | None = None
    model: str | None = None
    pci_address: str | None = None
    vendor_id: str | None = None
    device_id: str | None = None
    total_vram_bytes: int | None = None
    free_vram_bytes: int | None = None
    driver_version: str | None = None
    detection_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class HardwareProfile:
    os: OperatingSystem = field(default_factory=OperatingSystem)
    cpu: CPU = field(default_factory=CPU)
    memory: Memory = field(default_factory=Memory)
    gpus: tuple[GPU, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
