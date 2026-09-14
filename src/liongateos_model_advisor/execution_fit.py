"""Conservative GPU execution classification."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .memory_estimate import EstimateStatus, MemoryBudgetAssessment


MultiGPUStatus = Literal[
    "candidate",
    "not_needed",
    "unavailable",
    "unknown",
]


@dataclass(frozen=True)
class GPUExecutionClassification:
    single_gpu_status: EstimateStatus
    multi_gpu_status: MultiGPUStatus
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_gpu_execution(
    assessments: tuple[MemoryBudgetAssessment, ...],
    hardware,
    capability,
) -> GPUExecutionClassification:
    statuses = tuple(
        item.capacity_status
        for item in assessments
        if item.budget_kind == "gpu"
    )

    if "fits" in statuses:
        single_status = "fits"
    elif statuses and all(item == "does_not_fit" for item in statuses):
        single_status = "does_not_fit"
    else:
        single_status = "unknown"

    reasons = [f"single-gpu-{single_status}"]

    if single_status == "fits":
        multi_status = "not_needed"
    elif len(hardware.gpus) < 2:
        multi_status = "unavailable"
        reasons.append("multiple-gpus-not-discovered")
    elif capability is None:
        multi_status = "unknown"
        reasons.append("multi-gpu-runtime-capability-unknown")
    elif (
        capability.supports_multi_device is True
        and capability.supports_gpu_offload is True
    ):
        multi_status = "candidate"
        reasons.extend(
            (
                "runtime-declares-multi-device-offload",
                "multi-gpu-fit-not-proven",
            )
        )
    elif (
        capability.supports_multi_device is False
        or capability.supports_gpu_offload is False
    ):
        multi_status = "unavailable"
        reasons.append("runtime-does-not-declare-required-multi-gpu-capability")
    else:
        multi_status = "unknown"
        reasons.append("multi-gpu-runtime-capability-incomplete")

    return GPUExecutionClassification(
        single_gpu_status=single_status,
        multi_gpu_status=multi_status,
        reasons=tuple(reasons),
    )
