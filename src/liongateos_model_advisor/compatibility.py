"""Conservative hardware/runtime compatibility assessment."""

from __future__ import annotations

from dataclasses import dataclass

from .compatibility_profile import CompatibilityProfile, RuntimeCompatibility
from .hardware_profile import HardwareProfile
from .runtime_profile import RuntimeProfile


@dataclass(frozen=True)
class RuntimeCapabilityEvidence:
    runtime_name: str
    gpu_backend: str | None = None
    gpu_vendors: tuple[str, ...] = ()
    gpu_models: tuple[str, ...] = ()
    active_gpu_execution: bool = False
    supports_multi_device: bool | None = None
    supports_gpu_offload: bool | None = None
    supported_split_modes: tuple[str, ...] = ()
    supports_auto_fit: bool | None = None
    feature_source: str | None = None
    source: str | None = None


def assess_compatibility(
    hardware: HardwareProfile,
    runtimes: RuntimeProfile,
    evidence: tuple[RuntimeCapabilityEvidence, ...] = (),
) -> CompatibilityProfile:
    evidence_by_runtime = {
        item.runtime_name.lower(): item
        for item in evidence
    }

    hardware_vendors = {
        gpu.vendor.lower()
        for gpu in hardware.gpus
        if gpu.vendor
    }

    results: list[RuntimeCompatibility] = []

    for runtime in runtimes.runtimes:
        if not runtime.available:
            results.append(
                RuntimeCompatibility(
                    runtime_name=runtime.name,
                    status="unavailable",
                    reasons=("runtime-not-discovered",),
                    evidence_sources=("runtime-profile",),
                )
            )
            continue

        capability = evidence_by_runtime.get(runtime.name.lower())

        if capability and capability.active_gpu_execution:
            sources = ["hardware-profile", "runtime-profile"]
            if capability.source:
                sources.append(capability.source)

            results.append(
                RuntimeCompatibility(
                    runtime_name=runtime.name,
                    status="compatible",
                    reasons=("active-gpu-execution-observed",),
                    evidence_sources=tuple(sources),
                )
            )
            continue

        if capability and capability.gpu_backend:
            reported_vendors = {
                vendor.lower()
                for vendor in capability.gpu_vendors
            }

            if reported_vendors and reported_vendors.intersection(hardware_vendors):
                sources = ["hardware-profile", "runtime-profile"]
                if capability.source:
                    sources.append(capability.source)

                results.append(
                    RuntimeCompatibility(
                        runtime_name=runtime.name,
                        status="compatible",
                        reasons=(
                            f"runtime-reports-{capability.gpu_backend.lower()}-gpu-support",
                            "reported-gpu-vendor-matches-detected-hardware",
                        ),
                        evidence_sources=tuple(sources),
                    )
                )
                continue

        results.append(
            RuntimeCompatibility(
                runtime_name=runtime.name,
                status="unknown",
                reasons=("backend-capability-not-proven",),
                evidence_sources=("hardware-profile", "runtime-profile"),
            )
        )

    return CompatibilityProfile(
        hardware_schema_version=hardware.schema_version,
        runtime_schema_version=runtimes.schema_version,
        runtimes=tuple(results),
    )
