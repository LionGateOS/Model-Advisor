"""Normalized public model metadata profile for LionGateOS Model Advisor."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


MODEL_SCHEMA_VERSION = "1"

EvidenceKind = Literal[
    "reported",
    "derived",
    "assumed",
]

ArtifactLocation = Literal[
    "local",
    "remote",
    "unknown",
]

ModelSourceState = Literal[
    "available",
    "partial",
    "unavailable",
    "error",
]

_VALID_EVIDENCE_KINDS = {
    "reported",
    "derived",
    "assumed",
}

_VALID_ARTIFACT_LOCATIONS = {
    "local",
    "remote",
    "unknown",
}

_VALID_MODEL_SOURCE_STATES = {
    "available",
    "partial",
    "unavailable",
    "error",
}


@dataclass(frozen=True)
class MetadataEvidence:
    """Evidence attached to one normalized metadata field."""

    field: str
    source: str
    kind: EvidenceKind

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("metadata evidence field must not be empty")

        if not self.source:
            raise ValueError("metadata evidence source must not be empty")

        if self.kind not in _VALID_EVIDENCE_KINDS:
            raise ValueError(
                f"unsupported metadata evidence kind: {self.kind}"
            )


@dataclass(frozen=True)
class ModelSourceStatus:
    """Availability and completeness of one model metadata source."""

    source: str
    status: ModelSourceState
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("model source must not be empty")

        if self.status not in _VALID_MODEL_SOURCE_STATES:
            raise ValueError(
                f"unsupported model source status: {self.status}"
            )


@dataclass(frozen=True)
class ModelIdentity:
    """Normalized identity and model-level metadata."""

    model_id: str
    display_name: str | None = None
    family: str | None = None
    architecture: str | None = None
    parameter_count: int | None = None
    parameter_size_label: str | None = None
    active_parameter_count: int | None = None
    context_length: int | None = None
    tasks: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    license: str | None = None
    evidence: tuple[MetadataEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("model_id must not be empty")

        if self.parameter_count is not None and self.parameter_count <= 0:
            raise ValueError("parameter_count must be positive when known")

        if (
            self.active_parameter_count is not None
            and self.active_parameter_count <= 0
        ):
            raise ValueError(
                "active_parameter_count must be positive when known"
            )

        if (
            self.parameter_count is not None
            and self.active_parameter_count is not None
            and self.active_parameter_count > self.parameter_count
        ):
            raise ValueError(
                "active_parameter_count cannot exceed parameter_count"
            )

        if self.context_length is not None and self.context_length <= 0:
            raise ValueError("context_length must be positive when known")


@dataclass(frozen=True)
class ModelArtifact:
    """Normalized metadata for one concrete model artifact or variant."""

    artifact_id: str
    model_id: str
    digest: str | None = None
    location: ArtifactLocation = "unknown"
    format: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None
    evidence: tuple[MetadataEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("artifact_id must not be empty")

        if not self.model_id:
            raise ValueError("model_id must not be empty")

        if self.location not in _VALID_ARTIFACT_LOCATIONS:
            raise ValueError(
                f"unsupported artifact location: {self.location}"
            )

        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must not be negative")


@dataclass(frozen=True)
class ModelProfile:
    """Normalized collection of model identities and concrete artifacts."""

    models: tuple[ModelIdentity, ...] = ()
    artifacts: tuple[ModelArtifact, ...] = ()
    sources: tuple[ModelSourceStatus, ...] = ()
    schema_version: str = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        source_names = [source.source for source in self.sources]

        if len(source_names) != len(set(source_names)):
            raise ValueError("duplicate source in model profile")

        model_ids = [model.model_id for model in self.models]

        if len(model_ids) != len(set(model_ids)):
            raise ValueError("duplicate model_id in model profile")

        artifact_ids = [artifact.artifact_id for artifact in self.artifacts]

        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("duplicate artifact_id in model profile")

        known_models = set(model_ids)

        for artifact in self.artifacts:
            if artifact.model_id not in known_models:
                raise ValueError(
                    "artifact references unknown model_id: "
                    f"{artifact.model_id}"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
