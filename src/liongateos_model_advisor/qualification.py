"""Evidence-conservative model qualification."""

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .compatibility_profile import RuntimeCompatibility
from .execution_fit import GPUExecutionClassification


QualificationStatus = Literal[
    "qualified",
    "candidate",
    "not_qualified",
    "unknown",
]

ExecutionPath = Literal[
    "single_gpu",
    "multi_gpu",
    "none",
    "unknown",
]


@dataclass(frozen=True)
class ModelQualification:
    model_id: str
    artifact_id: str
    runtime_name: str
    status: QualificationStatus
    execution_path: ExecutionPath
    reasons: tuple[str, ...] = ()
    evidence_sources: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def qualify_gpu_model(
    *,
    model_id: str,
    artifact_id: str,
    runtime: RuntimeCompatibility,
    execution: GPUExecutionClassification,
) -> ModelQualification:
    """Qualify one model/runtime GPU path without inventing missing evidence."""

    reasons = list(runtime.reasons)
    reasons.extend(execution.reasons)

    if runtime.status in ("incompatible", "unavailable"):
        status = "not_qualified"
        path = "none"
    elif runtime.status != "compatible":
        status = "unknown"
        path = "unknown"
    elif execution.single_gpu_status == "fits":
        status = "qualified"
        path = "single_gpu"
    elif execution.multi_gpu_status == "candidate":
        status = "candidate"
        path = "multi_gpu"
    elif (
        execution.single_gpu_status == "does_not_fit"
        and execution.multi_gpu_status == "unavailable"
    ):
        status = "not_qualified"
        path = "none"
    else:
        status = "unknown"
        path = "unknown"

    return ModelQualification(
        model_id=model_id,
        artifact_id=artifact_id,
        runtime_name=runtime.runtime_name,
        status=status,
        execution_path=path,
        reasons=tuple(dict.fromkeys(reasons)),
        evidence_sources=runtime.evidence_sources,
    )


def qualify_gpu_model_from_evidence(
    *,
    estimate,
    hardware,
    runtime,
    capability,
):
    """Build qualification from existing memory and runtime evidence."""
    from .execution_fit import classify_gpu_execution
    from .fit_assessment import assess_gpu_budgets

    assessments = assess_gpu_budgets(estimate, hardware)
    execution = classify_gpu_execution(
        assessments,
        hardware,
        capability,
    )

    result = qualify_gpu_model(
        model_id=estimate.model_id,
        artifact_id=estimate.artifact_id,
        runtime=runtime,
        execution=execution,
    )

    evidence_sources = list(result.evidence_sources)

    for assessment in assessments:
        for item in assessment.evidence:
            if item.source not in evidence_sources:
                evidence_sources.append(item.source)

    return ModelQualification(
        model_id=result.model_id,
        artifact_id=result.artifact_id,
        runtime_name=result.runtime_name,
        status=result.status,
        execution_path=result.execution_path,
        reasons=result.reasons,
        evidence_sources=tuple(evidence_sources),
    )
