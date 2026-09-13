"""Read-only data assembly for the LionGateOS Model Advisor dashboard."""

from __future__ import annotations

from typing import Any, Sequence

from .capability_discovery import collect_runtime_capability_evidence
from .compatibility import assess_compatibility
from .discovery import discover_hardware
from .runtime_discovery import discover_runtimes


def collect_dashboard_data(
    runtime_paths: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Collect existing public profiles for dashboard presentation.

    This function does not implement hardware/runtime discovery or
    compatibility policy itself. Existing Model Advisor domain logic remains
    authoritative.
    """
    paths = list(runtime_paths or ())

    hardware = discover_hardware()
    runtimes = discover_runtimes(paths)
    evidence = collect_runtime_capability_evidence(runtimes, paths)
    compatibility = assess_compatibility(
        hardware,
        runtimes,
        evidence,
    )

    return {
        "hardware": hardware.to_dict(),
        "runtimes": runtimes.to_dict(),
        "compatibility": compatibility.to_dict(),
    }
