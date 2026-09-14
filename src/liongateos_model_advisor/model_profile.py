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
    block_count: int | None = None
    embedding_length: int | None = None
    attention_head_count: int | tuple[int, ...] | None = None
    attention_head_count_kv: int | tuple[int, ...] | None = None
    attention_key_length: int | None = None
    attention_value_length: int | None = None
    nextn_predict_layers: int | None = None
    full_attention_interval: int | None = None
    attention_recurrent_layers: tuple[bool, ...] | None = None
    attention_sliding_window: int | None = None
    ssm_conv_kernel: int | None = None
    ssm_group_count: int | None = None
    ssm_inner_size: int | None = None
    ssm_state_size: int | None = None
    ssm_time_step_rank: int | None = None
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

        for field_name, value in (
            ("block_count", self.block_count),
            ("embedding_length", self.embedding_length),
            ("attention_key_length", self.attention_key_length),
            ("attention_value_length", self.attention_value_length),
            ("nextn_predict_layers", self.nextn_predict_layers),
            ("full_attention_interval", self.full_attention_interval),
            ("attention_sliding_window", self.attention_sliding_window),
            ("ssm_conv_kernel", self.ssm_conv_kernel),
            ("ssm_group_count", self.ssm_group_count),
            ("ssm_inner_size", self.ssm_inner_size),
            ("ssm_state_size", self.ssm_state_size),
            ("ssm_time_step_rank", self.ssm_time_step_rank),
        ):
            if value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be positive when known"
                )

        for field_name, value in (
            ("attention_head_count", self.attention_head_count),
            ("attention_head_count_kv", self.attention_head_count_kv),
        ):
            if isinstance(value, tuple):
                if not value or any(item <= 0 for item in value):
                    raise ValueError(
                        f"{field_name} entries must be positive"
                    )
            elif value is not None and value <= 0:
                raise ValueError(
                    f"{field_name} must be positive when known"
                )

        if (
            self.nextn_predict_layers is not None
            and self.block_count is not None
            and self.nextn_predict_layers > self.block_count
        ):
            raise ValueError(
                "nextn_predict_layers cannot exceed block_count"
            )

        if self.attention_recurrent_layers is not None:
            if (
                not self.attention_recurrent_layers
                or not all(
                    isinstance(item, bool)
                    for item in self.attention_recurrent_layers
                )
            ):
                raise ValueError(
                    "attention_recurrent_layers must contain booleans"
                )

        if self.block_count is not None:
            for field_name, value in (
                ("attention_head_count", self.attention_head_count),
                ("attention_head_count_kv", self.attention_head_count_kv),
                (
                    "attention_recurrent_layers",
                    self.attention_recurrent_layers,
                ),
            ):
                if (
                    isinstance(value, tuple)
                    and len(value) != self.block_count
                ):
                    raise ValueError(
                        f"{field_name} layer count must match block_count"
                    )


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
class ModelOffering:
    """One hosted/provider model offering."""

    offering_id: str
    source: str
    provider_model_id: str
    model_id: str | None = None
    context_length: int | None = None
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()
    supported_parameters: tuple[str, ...] = ()
    evidence: tuple[MetadataEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.offering_id:
            raise ValueError("offering_id must not be empty")
        if not self.source:
            raise ValueError("offering source must not be empty")
        if not self.provider_model_id:
            raise ValueError("provider_model_id must not be empty")
        if self.context_length is not None and self.context_length <= 0:
            raise ValueError("offering context_length must be positive")


@dataclass(frozen=True)
class ModelProfile:
    """Normalized collection of model identities and concrete artifacts."""

    models: tuple[ModelIdentity, ...] = ()
    artifacts: tuple[ModelArtifact, ...] = ()
    offerings: tuple[ModelOffering, ...] = ()
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

        offering_ids = [item.offering_id for item in self.offerings]

        if len(offering_ids) != len(set(offering_ids)):
            raise ValueError("duplicate offering_id in model profile")

        known_models = set(model_ids)

        for offering in self.offerings:
            if offering.model_id is not None and offering.model_id not in known_models:
                raise ValueError("offering references unknown model_id: " + offering.model_id)

        for artifact in self.artifacts:
            if artifact.model_id not in known_models:
                raise ValueError(
                    "artifact references unknown model_id: "
                    f"{artifact.model_id}"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
