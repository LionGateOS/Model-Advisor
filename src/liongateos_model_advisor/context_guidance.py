"""Evidence-bounded context comparisons; no execution-fit promises."""

from dataclasses import asdict, dataclass
from typing import Any

from .fit_assessment import assess_gpu_budgets
from .memory_calculation import estimate_model_memory
from .model_profile import ModelArtifact, ModelIdentity


DEFAULT_CONTEXT_LENGTHS = (4096, 8192, 16384, 32768)


@dataclass(frozen=True)
class ContextOption:
    context_length: int
    context_status: str
    kv_cache_bytes: int | None
    total_memory_status: str
    gpu_assessments: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compare_context_options(
    model: ModelIdentity,
    artifact: ModelArtifact,
    hardware,
    *,
    context_lengths: tuple[int, ...] = DEFAULT_CONTEXT_LENGTHS,
    key_bytes_per_element: float | None = None,
    value_bytes_per_element: float | None = None,
) -> tuple[ContextOption, ...]:
    """Compare requested contexts without treating partial memory as fit."""
    if not context_lengths:
        raise ValueError("context_lengths must not be empty")
    if any(
        not isinstance(length, int)
        or isinstance(length, bool)
        or length <= 0
        for length in context_lengths
    ):
        raise ValueError("context lengths must be positive integers")

    options = []
    for length in context_lengths:
        estimate = estimate_model_memory(
            model,
            artifact,
            context_length=length,
            key_bytes_per_element=key_bytes_per_element,
            value_bytes_per_element=value_bytes_per_element,
        )
        if model.context_length is None:
            context_status = "unknown"
        elif length > model.context_length:
            context_status = "exceeds_reported_limit"
        else:
            context_status = "within_reported_limit"

        assessments = assess_gpu_budgets(estimate, hardware)
        reasons = list(estimate.reasons)
        if context_status == "unknown":
            reasons.append("reported-model-context-unknown")

        options.append(
            ContextOption(
                context_length=length,
                context_status=context_status,
                kv_cache_bytes=estimate.kv_cache_bytes,
                total_memory_status="unknown",
                gpu_assessments=tuple(
                    assessment.to_dict() for assessment in assessments
                ),
                reasons=tuple(dict.fromkeys(reasons)),
            )
        )

    return tuple(options)
