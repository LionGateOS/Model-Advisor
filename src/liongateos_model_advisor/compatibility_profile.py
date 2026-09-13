"""Normalized public compatibility profile for LionGateOS Model Advisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


COMPATIBILITY_SCHEMA_VERSION = "1"

CompatibilityStatus = Literal[
    "compatible",
    "incompatible",
    "unknown",
    "unavailable",
]

_VALID_STATUSES = {
    "compatible",
    "incompatible",
    "unknown",
    "unavailable",
}


@dataclass(frozen=True)
class RuntimeCompatibility:
    runtime_name: str
    status: CompatibilityStatus
    reasons: tuple[str, ...] = ()
    evidence_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"unsupported compatibility status: {self.status}")


@dataclass(frozen=True)
class CompatibilityProfile:
    hardware_schema_version: str
    runtime_schema_version: str
    runtimes: tuple[RuntimeCompatibility, ...] = ()
    schema_version: str = COMPATIBILITY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
