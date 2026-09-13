"""Normalized public runtime profile for LionGateOS Model Advisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


RUNTIME_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class Runtime:
    name: str
    available: bool
    version: str | None = None
    build: str | None = None
    commit: str | None = None
    executables: tuple[str, ...] = ()
    discovery_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeProfile:
    runtimes: tuple[Runtime, ...] = ()
    schema_version: str = RUNTIME_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
