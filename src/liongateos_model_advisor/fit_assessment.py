"""Conservative model-memory fit assessment."""

from .memory_estimate import (
    BudgetKind,
    EstimateEvidence,
    MemoryBudgetAssessment,
    ModelMemoryEstimate,
)


def _assess_limit(
    estimate: ModelMemoryEstimate,
    limit: int | None,
    label: str,
):
    if limit is None:
        return "unknown", None, f"{label}-unknown"

    if estimate.estimated_total_bytes is not None:
        headroom = limit - estimate.estimated_total_bytes
        status = "fits" if headroom >= 0 else "does_not_fit"
        return status, headroom, f"estimated-total-{status}-{label}"

    minimum = estimate.known_minimum_bytes
    if minimum is None:
        return "unknown", None, "model-memory-requirement-unknown"

    if minimum > limit:
        return (
            "does_not_fit",
            limit - minimum,
            f"known-minimum-exceeds-{label}",
        )

    return (
        "unknown",
        None,
        f"known-minimum-fits-{label}-but-total-unknown",
    )


def assess_memory_budget(
    estimate: ModelMemoryEstimate,
    *,
    budget_kind: BudgetKind,
    target_id: str,
    capacity_bytes: int | None,
    available_bytes: int | None,
) -> MemoryBudgetAssessment:
    """Compare evidenced model memory with one hardware memory budget."""

    capacity_status, capacity_headroom, capacity_reason = _assess_limit(
        estimate, capacity_bytes, "capacity"
    )
    availability_status, available_headroom, availability_reason = (
        _assess_limit(estimate, available_bytes, "available-memory")
    )

    evidence = list(estimate.evidence)
    if capacity_bytes is not None:
        evidence.append(
            EstimateEvidence(
                field="capacity_bytes",
                source="hardware-profile",
                kind="reported",
            )
        )
    if available_bytes is not None:
        evidence.append(
            EstimateEvidence(
                field="available_bytes",
                source="hardware-profile",
                kind="reported",
            )
        )

    return MemoryBudgetAssessment(
        model_id=estimate.model_id,
        artifact_id=estimate.artifact_id,
        budget_kind=budget_kind,
        target_id=target_id,
        capacity_bytes=capacity_bytes,
        available_bytes=available_bytes,
        capacity_headroom_bytes=capacity_headroom,
        available_headroom_bytes=available_headroom,
        capacity_status=capacity_status,
        availability_status=availability_status,
        reasons=(capacity_reason, availability_reason),
        evidence=tuple(evidence),
    )


def assess_gpu_budgets(estimate, hardware):
    """Assess each discovered GPU independently; never pool VRAM implicitly."""
    results = []

    for index, gpu in enumerate(hardware.gpus):
        target_id = gpu.pci_address or f"gpu:{index}"
        results.append(
            assess_memory_budget(
                estimate,
                budget_kind="gpu",
                target_id=target_id,
                capacity_bytes=gpu.total_vram_bytes,
                available_bytes=gpu.free_vram_bytes,
            )
        )

    return tuple(results)
