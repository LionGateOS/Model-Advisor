"""Public memory-estimation contracts for LionGateOS Model Advisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


MEMORY_ESTIMATE_SCHEMA_VERSION = "1"

EstimateStatus = Literal[
    "fits",
    "does_not_fit",
    "unknown",
]

BudgetKind = Literal[
    "gpu",
    "system-memory",
]

EstimateEvidenceKind = Literal[
    "reported",
    "derived",
    "assumed",
]

_VALID_STATUSES = {
    "fits",
    "does_not_fit",
    "unknown",
}

_VALID_BUDGET_KINDS = {
    "gpu",
    "system-memory",
}

_VALID_EVIDENCE_KINDS = {
    "reported",
    "derived",
    "assumed",
}


@dataclass(frozen=True)
class EstimateEvidence:
    """Evidence supporting one memory-estimation field."""

    field: str
    source: str
    kind: EstimateEvidenceKind

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("estimate evidence field must not be empty")

        if not self.source:
            raise ValueError("estimate evidence source must not be empty")

        if self.kind not in _VALID_EVIDENCE_KINDS:
            raise ValueError(
                f"unsupported estimate evidence kind: {self.kind}"
            )


@dataclass(frozen=True)
class ModelMemoryEstimate:
    """Explainable memory components for one model artifact and context."""

    model_id: str
    artifact_id: str
    context_length: int

    weight_bytes: int | None = None
    kv_cache_bytes: int | None = None
    kv_key_bytes_per_element: float | None = None
    kv_value_bytes_per_element: float | None = None
    recurrent_state_bytes: int | None = None
    runtime_overhead_bytes: int | None = None

    known_minimum_bytes: int | None = None
    estimated_total_bytes: int | None = None

    reasons: tuple[str, ...] = ()
    evidence: tuple[EstimateEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must not be empty")

        if not self.artifact_id:
            raise ValueError("artifact_id must not be empty")

        if self.context_length <= 0:
            raise ValueError("context_length must be positive")

        for field_name, value in (
            ("weight_bytes", self.weight_bytes),
            ("kv_cache_bytes", self.kv_cache_bytes),
            ("recurrent_state_bytes", self.recurrent_state_bytes),
            ("runtime_overhead_bytes", self.runtime_overhead_bytes),
            ("known_minimum_bytes", self.known_minimum_bytes),
            ("estimated_total_bytes", self.estimated_total_bytes),
        ):
            if value is not None and value < 0:
                raise ValueError(
                    f"{field_name} must not be negative when known"
                )

        for field_name, value in (
            (
                "kv_key_bytes_per_element",
                self.kv_key_bytes_per_element,
            ),
            (
                "kv_value_bytes_per_element",
                self.kv_value_bytes_per_element,
            ),
        ):
            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be positive when known"
                )

        if (
            self.kv_key_bytes_per_element is None
        ) != (
            self.kv_value_bytes_per_element is None
        ):
            raise ValueError(
                "KV key and value element sizes must be known together"
            )

        if (
            self.kv_cache_bytes is not None
            and self.kv_key_bytes_per_element is None
        ):
            raise ValueError(
                "known kv_cache_bytes requires explicit K/V element sizes"
            )

        known_components = (
            self.weight_bytes,
            self.kv_cache_bytes,
            self.recurrent_state_bytes,
            self.runtime_overhead_bytes,
        )
        known_sum = sum(
            value for value in known_components if value is not None
        )

        if (
            self.known_minimum_bytes is not None
            and self.known_minimum_bytes < known_sum
        ):
            raise ValueError(
                "known_minimum_bytes cannot be below known components"
            )

        if (
            self.estimated_total_bytes is not None
            and self.known_minimum_bytes is not None
            and self.estimated_total_bytes < self.known_minimum_bytes
        ):
            raise ValueError(
                "estimated_total_bytes cannot be below known minimum"
            )

        if (
            self.estimated_total_bytes is not None
            and any(value is None for value in known_components)
        ):
            raise ValueError(
                "estimated_total_bytes requires all memory components"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryBudgetAssessment:
    """Compare one model-memory estimate with one explicit memory budget."""

    model_id: str
    artifact_id: str
    budget_kind: BudgetKind
    target_id: str

    capacity_bytes: int | None = None
    available_bytes: int | None = None

    capacity_headroom_bytes: int | None = None
    available_headroom_bytes: int | None = None

    capacity_status: EstimateStatus = "unknown"
    availability_status: EstimateStatus = "unknown"

    reasons: tuple[str, ...] = ()
    evidence: tuple[EstimateEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must not be empty")

        if not self.artifact_id:
            raise ValueError("artifact_id must not be empty")

        if self.budget_kind not in _VALID_BUDGET_KINDS:
            raise ValueError(
                f"unsupported memory budget kind: {self.budget_kind}"
            )

        if not self.target_id:
            raise ValueError("target_id must not be empty")

        for field_name, value in (
            ("capacity_bytes", self.capacity_bytes),
            ("available_bytes", self.available_bytes),
        ):
            if value is not None and value < 0:
                raise ValueError(
                    f"{field_name} must not be negative when known"
                )

        for field_name, value in (
            ("capacity_status", self.capacity_status),
            ("availability_status", self.availability_status),
        ):
            if value not in _VALID_STATUSES:
                raise ValueError(
                    f"unsupported {field_name}: {value}"
                )

        if (
            self.capacity_bytes is not None
            and self.available_bytes is not None
            and self.available_bytes > self.capacity_bytes
        ):
            raise ValueError(
                "available_bytes cannot exceed capacity_bytes"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
