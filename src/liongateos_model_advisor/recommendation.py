"""Evidence-conservative, workload-specific local model recommendations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .model_profile import ModelArtifact, ModelIdentity
from .qualification import ModelQualification


RecommendationStatus = Literal[
    "supported_candidate",
    "needs_hardware_verification",
    "workload_unknown",
    "not_recommended",
]

_WORKLOAD_TASKS = {
    "coding": frozenset({"code-generation", "text-to-code"}),
    "general_chat": frozenset({"conversational"}),
    "reasoning": frozenset({"reasoning"}),
}


@dataclass(frozen=True)
class ModelRecommendation:
    model_id: str
    artifact_id: str
    workload: str
    status: RecommendationStatus
    reasons: tuple[str, ...]
    evidence_sources: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def recommend_local_model(
    *,
    model: ModelIdentity,
    artifact: ModelArtifact,
    qualification: ModelQualification,
    workload: str,
) -> ModelRecommendation:
    """Classify one local artifact without inventing missing evidence."""

    if workload not in _WORKLOAD_TASKS:
        raise ValueError("unsupported workload")

    if model.model_id != artifact.model_id:
        raise ValueError("model and artifact identities differ")

    if qualification.model_id != model.model_id:
        raise ValueError("qualification model identity differs")

    if qualification.artifact_id != artifact.artifact_id:
        raise ValueError("qualification artifact identity differs")

    if artifact.location != "local":
        raise ValueError("local recommendations require a local artifact")

    reasons = []
    evidence = list(qualification.evidence_sources)

    if qualification.status == "not_qualified":
        status = "not_recommended"
        reasons.append("Current runtime or hardware evidence does not qualify this artifact")
    else:
        matching_tasks = _WORKLOAD_TASKS[workload]
        reported_tasks = set(model.tasks)
        reported_capabilities = set(model.capabilities)

        matched_fields = set()
        if matching_tasks.intersection(reported_tasks):
            matched_fields.add("tasks")
        if matching_tasks.intersection(reported_capabilities):
            matched_fields.add("capabilities")

        workload_evidence = tuple(
            item.source
            for item in model.evidence
            if item.field in matched_fields
            and item.kind == "reported"
        )

        if not workload_evidence:
            status = "workload_unknown"
            reasons.append("No sufficiently sourced workload match")
        elif qualification.status == "qualified":
            status = "supported_candidate"
            reasons.append("Workload metadata matches and existing qualification is positive")
        else:
            status = "needs_hardware_verification"
            reasons.append("Workload metadata matches but hardware qualification is incomplete")

        evidence.extend(workload_evidence)

    return ModelRecommendation(
        model_id=model.model_id,
        artifact_id=artifact.artifact_id,
        workload=workload,
        status=status,
        reasons=tuple(reasons),
        evidence_sources=tuple(dict.fromkeys(evidence)),
    )
