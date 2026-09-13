"""Normalize upstream model metadata into public Model Advisor profiles."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .model_profile import (
    ArtifactLocation,
    MetadataEvidence,
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
)


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int) and value > 0:
        return value

    return None


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()

    result: list[str] = []

    for item in value:
        cleaned = _clean_string(item)

        if cleaned is not None and cleaned not in result:
            result.append(cleaned)

    return tuple(result)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    return {}


def profile_from_huggingface_model_info(
    payload: Mapping[str, Any],
) -> ModelProfile:
    """Normalize a Hugging Face model-info payload.

    This adapter deliberately does not infer parameter counts from model names
    or size labels. Exact counts are accepted only from structured metadata.
    """

    repo_id = (
        _clean_string(payload.get("id"))
        or _clean_string(payload.get("modelId"))
    )

    if repo_id is None:
        raise ValueError("Hugging Face model info must include an id")

    model_id = f"huggingface:{repo_id}"
    source = f"huggingface:model-info:{repo_id}"
    evidence: list[MetadataEvidence] = []

    card_data = _mapping(payload.get("cardData"))
    tags = _strings(payload.get("tags"))

    display_name = _clean_string(card_data.get("model_name"))

    if display_name is not None:
        evidence.append(
            MetadataEvidence(
                field="display_name",
                source=source,
                kind="reported",
            )
        )

    pipeline_tag = (
        _clean_string(payload.get("pipeline_tag"))
        or _clean_string(card_data.get("pipeline_tag"))
    )
    tasks = (pipeline_tag,) if pipeline_tag is not None else ()

    if tasks:
        evidence.append(
            MetadataEvidence(
                field="tasks",
                source=source,
                kind="reported",
            )
        )

    license_name = _clean_string(card_data.get("license"))

    if license_name is None:
        for tag in tags:
            if tag.casefold().startswith("license:"):
                candidate = tag.split(":", 1)[1].strip()

                if candidate:
                    license_name = candidate
                    break

    if license_name is not None:
        evidence.append(
            MetadataEvidence(
                field="license",
                source=source,
                kind="reported",
            )
        )

    safetensors = _mapping(payload.get("safetensors"))
    parameter_count = _positive_int(safetensors.get("total"))
    parameter_kind = "reported"

    if parameter_count is None:
        parameters = _mapping(safetensors.get("parameters"))

        if parameters:
            values = list(parameters.values())

            if all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
                for value in values
            ):
                derived_total = sum(values)

                if derived_total > 0:
                    parameter_count = derived_total
                    parameter_kind = "derived"

    if parameter_count is not None:
        evidence.append(
            MetadataEvidence(
                field="parameter_count",
                source=f"{source}:safetensors",
                kind=parameter_kind,
            )
        )

    artifacts: tuple[ModelArtifact, ...] = ()

    if safetensors:
        artifacts = (
            ModelArtifact(
                artifact_id=f"{model_id}:safetensors",
                model_id=model_id,
                format="safetensors",
                evidence=(
                    MetadataEvidence(
                        field="format",
                        source=f"{source}:safetensors",
                        kind="reported",
                    ),
                ),
            ),
        )

    return ModelProfile(
        models=(
            ModelIdentity(
                model_id=model_id,
                display_name=display_name,
                parameter_count=parameter_count,
                tasks=tasks,
                license=license_name,
                evidence=tuple(evidence),
            ),
        ),
        artifacts=artifacts,
    )


def profile_from_ollama_show(
    model_name: str,
    payload: Mapping[str, Any],
    *,
    size_bytes: int | None = None,
    digest: str | None = None,
    artifact_location: ArtifactLocation = "unknown",
) -> ModelProfile:
    """Normalize one Ollama show-model response.

    Approximate labels such as ``4.3B`` remain labels. They are never promoted
    to exact parameter counts.
    """

    model_name = model_name.strip()

    if not model_name:
        raise ValueError("Ollama model name must not be empty")

    model_id = f"ollama:{model_name}"
    source = f"ollama:show:{model_name}"

    details = _mapping(payload.get("details"))
    model_info = _mapping(payload.get("model_info"))

    family = _clean_string(details.get("family"))
    architecture = _clean_string(model_info.get("general.architecture"))
    parameter_size_label = _clean_string(details.get("parameter_size"))
    parameter_count = _positive_int(
        model_info.get("general.parameter_count")
    )

    context_length = None
    context_source = None

    if architecture is not None:
        context_key = f"{architecture}.context_length"
        context_length = _positive_int(model_info.get(context_key))

        if context_length is not None:
            context_source = f"{source}:model_info:{context_key}"

    if context_length is None:
        context_length = _positive_int(details.get("context_length"))

        if context_length is not None:
            context_source = f"{source}:details:context_length"

    capabilities = _strings(payload.get("capabilities"))

    license_name = _clean_string(model_info.get("general.license"))

    evidence: list[MetadataEvidence] = []

    for field, value, evidence_source in (
        ("family", family, f"{source}:details:family"),
        (
            "architecture",
            architecture,
            f"{source}:model_info:general.architecture",
        ),
        (
            "parameter_size_label",
            parameter_size_label,
            f"{source}:details:parameter_size",
        ),
        (
            "parameter_count",
            parameter_count,
            f"{source}:model_info:general.parameter_count",
        ),
        ("context_length", context_length, context_source),
        ("capabilities", capabilities, f"{source}:capabilities"),
        (
            "license",
            license_name,
            f"{source}:model_info:general.license",
        ),
    ):
        if value not in (None, (), "") and evidence_source is not None:
            evidence.append(
                MetadataEvidence(
                    field=field,
                    source=evidence_source,
                    kind="reported",
                )
            )

    artifact_evidence: list[MetadataEvidence] = []

    if artifact_location != "unknown":
        artifact_evidence.append(
            MetadataEvidence(
                field="location",
                source=f"{source}:model-list-registration",
                kind="derived",
            )
        )

    artifact_format = _clean_string(details.get("format"))
    quantization = _clean_string(details.get("quantization_level"))
    cleaned_digest = _clean_string(digest)

    if cleaned_digest is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="digest",
                source=f"{source}:model-list-digest",
                kind="reported",
            )
        )

    if artifact_format is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="format",
                source=f"{source}:details:format",
                kind="reported",
            )
        )

    if quantization is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="quantization",
                source=f"{source}:details:quantization_level",
                kind="reported",
            )
        )

    if size_bytes is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="size_bytes",
                source=f"{source}:model-list-size",
                kind="reported",
            )
        )

    return ModelProfile(
        models=(
            ModelIdentity(
                model_id=model_id,
                family=family,
                architecture=architecture,
                parameter_count=parameter_count,
                parameter_size_label=parameter_size_label,
                context_length=context_length,
                capabilities=capabilities,
                license=license_name,
                evidence=tuple(evidence),
            ),
        ),
        artifacts=(
            ModelArtifact(
                artifact_id=f"{model_id}:artifact",
                model_id=model_id,
                digest=cleaned_digest,
                location=artifact_location,
                format=artifact_format,
                quantization=quantization,
                size_bytes=size_bytes,
                evidence=tuple(artifact_evidence),
            ),
        ),
    )


def profile_from_gguf_metadata(
    *,
    model_id: str,
    artifact_id: str,
    metadata: Mapping[str, Any],
    size_bytes: int | None = None,
    quantization: str | None = None,
) -> ModelProfile:
    """Normalize standardized GGUF metadata supplied by a trusted parser."""

    model_id = model_id.strip()
    artifact_id = artifact_id.strip()

    if not model_id:
        raise ValueError("GGUF model_id must not be empty")

    if not artifact_id:
        raise ValueError("GGUF artifact_id must not be empty")

    source = f"gguf:{artifact_id}"

    display_name = _clean_string(metadata.get("general.name"))
    architecture = _clean_string(metadata.get("general.architecture"))
    parameter_count = _positive_int(
        metadata.get("general.parameter_count")
    )
    parameter_size_label = _clean_string(
        metadata.get("general.size_label")
    )
    license_name = _clean_string(metadata.get("general.license"))

    context_length = None
    context_key = None

    if architecture is not None:
        context_key = f"{architecture}.context_length"
        context_length = _positive_int(metadata.get(context_key))

    evidence: list[MetadataEvidence] = []

    for field, value, key in (
        ("display_name", display_name, "general.name"),
        ("architecture", architecture, "general.architecture"),
        (
            "parameter_count",
            parameter_count,
            "general.parameter_count",
        ),
        (
            "parameter_size_label",
            parameter_size_label,
            "general.size_label",
        ),
        ("license", license_name, "general.license"),
    ):
        if value is not None:
            evidence.append(
                MetadataEvidence(
                    field=field,
                    source=f"{source}:{key}",
                    kind="reported",
                )
            )

    if context_length is not None and context_key is not None:
        evidence.append(
            MetadataEvidence(
                field="context_length",
                source=f"{source}:{context_key}",
                kind="reported",
            )
        )

    artifact_evidence = [
        MetadataEvidence(
            field="format",
            source=source,
            kind="reported",
        )
    ]

    cleaned_quantization = _clean_string(quantization)

    if cleaned_quantization is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="quantization",
                source=f"{source}:trusted-parser",
                kind="reported",
            )
        )

    if size_bytes is not None:
        artifact_evidence.append(
            MetadataEvidence(
                field="size_bytes",
                source=f"{source}:filesystem",
                kind="reported",
            )
        )

    return ModelProfile(
        models=(
            ModelIdentity(
                model_id=model_id,
                display_name=display_name,
                architecture=architecture,
                parameter_count=parameter_count,
                parameter_size_label=parameter_size_label,
                context_length=context_length,
                license=license_name,
                evidence=tuple(evidence),
            ),
        ),
        artifacts=(
            ModelArtifact(
                artifact_id=artifact_id,
                model_id=model_id,
                format="gguf",
                quantization=cleaned_quantization,
                size_bytes=size_bytes,
                evidence=tuple(artifact_evidence),
            ),
        ),
    )
