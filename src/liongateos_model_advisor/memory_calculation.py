"""Evidence-bounded model memory calculations."""

from __future__ import annotations

import math

from .memory_estimate import (
    EstimateEvidence,
    ModelMemoryEstimate,
)
from .model_profile import ModelArtifact, ModelIdentity


def _recurrent_metadata_present(model: ModelIdentity) -> bool:
    return any(
        value is not None
        for value in (
            model.ssm_conv_kernel,
            model.ssm_group_count,
            model.ssm_inner_size,
            model.ssm_state_size,
            model.ssm_time_step_rank,
        )
    )


def _full_attention_indices(
    model: ModelIdentity,
) -> tuple[tuple[int, ...] | None, str | None]:
    """Return evidenced full-attention trunk layers.

    No architecture-name guessing is performed.
    """

    if model.block_count is None:
        return None, "block-count-unknown"

    nextn = model.nextn_predict_layers or 0
    trunk_layers = model.block_count - nextn

    if trunk_layers <= 0:
        return None, "execution-trunk-layer-count-unknown"

    if model.attention_sliding_window is not None:
        return None, "sliding-window-layer-pattern-unsupported"

    if model.attention_recurrent_layers is not None:
        recurrent = model.attention_recurrent_layers[:trunk_layers]
        return (
            tuple(
                index
                for index, is_recurrent in enumerate(recurrent)
                if not is_recurrent
            ),
            None,
        )

    if model.full_attention_interval is not None:
        interval = model.full_attention_interval
        return (
            tuple(
                index
                for index in range(trunk_layers)
                if (index + 1) % interval == 0
            ),
            None,
        )

    return None, "attention-layer-topology-unknown"


def calculate_kv_cache_bytes(
    model: ModelIdentity,
    *,
    context_length: int,
    key_bytes_per_element: float,
    value_bytes_per_element: float,
) -> tuple[int | None, tuple[str, ...]]:
    """Calculate context-scaled KV bytes only when topology is evidenced."""

    if context_length <= 0:
        raise ValueError("context_length must be positive")

    if key_bytes_per_element <= 0:
        raise ValueError("key_bytes_per_element must be positive")

    if value_bytes_per_element <= 0:
        raise ValueError("value_bytes_per_element must be positive")

    if model.attention_head_count_kv is None:
        return None, ("kv-head-count-unknown",)

    if model.attention_key_length is None:
        return None, ("attention-key-length-unknown",)

    if model.attention_value_length is None:
        return None, ("attention-value-length-unknown",)

    full_attention_indices, topology_reason = _full_attention_indices(
        model
    )

    if full_attention_indices is None:
        return None, (topology_reason or "attention-topology-unknown",)

    if not full_attention_indices:
        return 0, ()

    kv_heads = model.attention_head_count_kv

    if isinstance(kv_heads, tuple):
        selected_kv_heads = sum(
            kv_heads[index]
            for index in full_attention_indices
        )
    else:
        selected_kv_heads = (
            kv_heads * len(full_attention_indices)
        )

    per_head_token_bytes = (
        model.attention_key_length * key_bytes_per_element
        + model.attention_value_length * value_bytes_per_element
    )

    calculated = (
        context_length
        * selected_kv_heads
        * per_head_token_bytes
    )

    return math.ceil(calculated), ()


def estimate_model_memory(
    model: ModelIdentity,
    artifact: ModelArtifact,
    *,
    context_length: int,
    key_bytes_per_element: float | None = None,
    value_bytes_per_element: float | None = None,
) -> ModelMemoryEstimate:
    """Build a conservative estimate without inventing missing evidence."""

    if artifact.model_id != model.model_id:
        raise ValueError(
            "artifact model_id must match model identity"
        )

    if context_length <= 0:
        raise ValueError("context_length must be positive")

    if (
        key_bytes_per_element is None
    ) != (
        value_bytes_per_element is None
    ):
        raise ValueError(
            "KV key and value element sizes must be supplied together"
        )

    reasons: list[str] = []
    evidence: list[EstimateEvidence] = []

    # Artifact/file size is storage evidence. It is intentionally not
    # promoted to resident weight memory.
    weight_bytes = None

    if artifact.size_bytes is not None:
        reasons.append(
            "artifact-size-is-storage-not-resident-weight-proof"
        )
    else:
        reasons.append("resident-weight-memory-unknown")

    kv_cache_bytes = None

    if key_bytes_per_element is None:
        reasons.append("kv-element-size-unknown")
    else:
        kv_cache_bytes, kv_reasons = calculate_kv_cache_bytes(
            model,
            context_length=context_length,
            key_bytes_per_element=key_bytes_per_element,
            value_bytes_per_element=value_bytes_per_element,
        )
        reasons.extend(kv_reasons)

        evidence.extend(
            (
                EstimateEvidence(
                    field="kv_key_bytes_per_element",
                    source="explicit-kv-element-size",
                    kind="assumed",
                ),
                EstimateEvidence(
                    field="kv_value_bytes_per_element",
                    source="explicit-kv-element-size",
                    kind="assumed",
                ),
            )
        )

        if kv_cache_bytes is not None:
            evidence.append(
                EstimateEvidence(
                    field="kv_cache_bytes",
                    source="reported-attention-geometry",
                    kind="derived",
                )
            )

    recurrent_state_bytes = None

    if (
        _recurrent_metadata_present(model)
        or model.attention_recurrent_layers is not None
        or model.full_attention_interval is not None
    ):
        reasons.append("recurrent-state-memory-unknown")

    reasons.append("runtime-overhead-unknown")

    if (
        model.context_length is not None
        and context_length > model.context_length
    ):
        reasons.append(
            "requested-context-exceeds-reported-model-context"
        )

    known_minimum_bytes = kv_cache_bytes

    return ModelMemoryEstimate(
        model_id=model.model_id,
        artifact_id=artifact.artifact_id,
        context_length=context_length,
        weight_bytes=weight_bytes,
        kv_cache_bytes=kv_cache_bytes,
        kv_key_bytes_per_element=key_bytes_per_element,
        kv_value_bytes_per_element=value_bytes_per_element,
        recurrent_state_bytes=recurrent_state_bytes,
        runtime_overhead_bytes=None,
        known_minimum_bytes=known_minimum_bytes,
        estimated_total_bytes=None,
        reasons=tuple(dict.fromkeys(reasons)),
        evidence=tuple(evidence),
    )
