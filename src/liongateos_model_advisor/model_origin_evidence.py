"""Local model-origin evidence validation (V1, read-only, fail-closed).

Scope of this milestone (M09A)
------------------------------
Validate one specific local Ollama artifact identity against explicit,
structured origin evidence records, and produce an explicit evidence result.

The ONLY verification actually established by this validator is local and
bounded: the SHA-256 of the small local Ollama manifest file is recomputed
and compared against the manifest digest recorded for the artifact, and the
manifest's single model layer must chain to the recorded model-layer digest.
That is a real, reproducible digest check over a small file — never over a
model weight blob.

What V1 deliberately does NOT claim
-----------------------------------
- No upstream-origin verification. ``upstream_origin_verified`` is always
  ``False`` in V1. Any upstream-origin string carried by an evidence record
  is preserved as a CLAIM only and is never treated as proof. This module
  does not match local artifacts against Hugging Face repositories and does
  not make real-world Ollama-to-Hugging-Face matching operational.
- No model blob verification. The (large) model layer blob is never read or
  hashed, so modification of model weight bytes is out of scope here.
- No network requests, downloads, launches, installations, deletions, or
  writes of any kind.
- Matching model names, tags, architectures, quantizations, sizes, or URLs
  are never accepted as proof of origin.

Trust root
----------
The only supported trust root is the constant
``LOCAL_MANIFEST_DIGEST_TRUST_ROOT``: the assumption that a manifest digest
recorded locally by the Ollama registry for a pulled manifest is an accurate
record of what the local registry received at pull time. Evidence must be
anchored under this explicitly declared trust root; any other trust-root
value is rejected. Test fixtures that simulate evidence must use this same
constant and must be clearly labelled as simulated, not as verified
real-world provenance.

Result contract
---------------
The result status is ``anchored`` only when every local check succeeds, and
``rejected`` in every other case (fail closed). Missing, ambiguous,
conflicting, stale, mismatched, or malformed evidence, and unverifiable
conditions, all yield ``rejected`` with deterministic machine-code reasons.
Reason strings never contain local filesystem paths, timestamps, evidence
values, or other potentially private material.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from .ollama_manifest_identity import (
    _DIGEST,
    _MODEL_LAYER,
    _is_safe_component,
    _model_path_parts,
)


LOCAL_MANIFEST_DIGEST_TRUST_ROOT = "local-ollama-manifest-digest-record"

LOCAL_EVIDENCE_SOURCE = "local-registry-manifest-record"

_MANIFEST_MAX_BYTES = 1024 * 1024

_DEFAULT_MAX_AGE_SECONDS = 30 * 24 * 60 * 60

OriginEvidenceStatus = Literal["anchored", "rejected"]

_ANCHORED_REASONS = (
    "local_manifest_digest_match",
    "model_layer_digest_chain_match",
    "model_blob_content_not_verified",
    "upstream_origin_not_verified",
)


@dataclass(frozen=True)
class ArtifactOriginRecord:
    """The identity claim for one local artifact to be validated."""

    model_name: str
    location: str
    registry_identity: str | None = None
    manifest_digest: str | None = None
    model_layer_digest: str | None = None


@dataclass(frozen=True)
class OriginEvidenceRecord:
    """One structured evidence record describing a pulled local artifact.

    ``captured_at`` is the epoch-seconds timestamp of the pull-time record
    and is required for staleness decisions; evidence without a usable
    timestamp cannot be anchored.
    """

    source: str
    registry_identity: str
    manifest_digest: str
    model_layer_digest: str
    upstream_origin: str | None = None
    captured_at: float | None = None


@dataclass(frozen=True)
class OriginEvidenceResult:
    """Explicit, fail-closed evidence result for one local artifact."""

    model_name: str | None
    registry_identity: str | None
    status: OriginEvidenceStatus
    reasons: tuple[str, ...]
    verified_manifest_digest: str | None = None
    model_layer_digest: str | None = None
    upstream_origin_claim: str | None = None
    upstream_origin_verified: bool = False
    trust_root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _well_formed_digest(value: object) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _registry_identity_parts(
    value: object,
) -> tuple[str, ...] | None:
    if not isinstance(value, str):
        return None

    parts = tuple(value.split("/"))
    if len(parts) < 2:
        return None
    if any(not part or not _is_safe_component(part) for part in parts):
        return None
    return parts


def _default_manifest_reader(manifest_path: Path) -> bytes:
    """Read a small manifest file with a strict size cap."""

    if not manifest_path.is_file():
        raise OSError("not a file")

    with manifest_path.open("rb") as handle:
        data = handle.read(_MANIFEST_MAX_BYTES + 1)

    if len(data) > _MANIFEST_MAX_BYTES:
        raise OSError("manifest exceeds size cap")
    return data


def _reject(
    model_name: str | None,
    registry_identity: str | None,
    reasons: tuple[str, ...],
    *,
    upstream_origin_claim: str | None = None,
) -> OriginEvidenceResult:
    return OriginEvidenceResult(
        model_name=model_name,
        registry_identity=registry_identity,
        status="rejected",
        reasons=reasons,
        upstream_origin_claim=upstream_origin_claim,
        upstream_origin_verified=False,
    )


def validate_local_origin_evidence(
    *,
    artifact: ArtifactOriginRecord,
    evidence_records: Sequence[OriginEvidenceRecord],
    trust_root: str,
    now: float,
    manifest_path: Path | None = None,
    manifest_reader: Callable[[Path], bytes] | None = None,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
) -> OriginEvidenceResult:
    """Validate origin evidence for one specific local Ollama artifact.

    Fails closed with a ``rejected`` result whenever verification cannot be
    completed. Never raises for invalid input; never touches the network.
    """

    # The documented trust root must be declared explicitly. Anything else,
    # including invented or implicit trust anchors, is rejected.
    if trust_root != LOCAL_MANIFEST_DIGEST_TRUST_ROOT:
        return _reject(None, None, ("unsupported_trust_root",))

    if not isinstance(artifact, ArtifactOriginRecord):
        return _reject(None, None, ("malformed_artifact_claim",))

    if artifact.location != "local":
        return _reject(None, None, ("remote_artifact_out_of_scope",))

    model_name: str | None = None
    if not isinstance(artifact.model_name, str) or (
        _model_path_parts(artifact.model_name) is None
    ):
        return _reject(None, None, ("malformed_artifact_identity",))
    model_name = artifact.model_name.strip()

    registry_parts = _registry_identity_parts(artifact.registry_identity)
    if registry_parts is None:
        return _reject(model_name, None, ("malformed_artifact_registry_identity",))
    registry_identity_value = artifact.registry_identity
    assert isinstance(registry_identity_value, str)

    # The registration name must be consistent with the registry identity it
    # claims (name-derived parts must be a suffix of the identity path).
    if name_parts := _model_path_parts(artifact.model_name):
        if name_parts != registry_parts[-len(name_parts):]:
            return _reject(
                model_name,
                registry_identity_value,
                ("artifact_name_registry_mismatch",),
            )

    # The artifact claim must itself carry digests to cross-check against;
    # missing records fail closed rather than being guessed.
    if artifact.manifest_digest is None:
        return _reject(
            model_name,
            registry_identity_value,
            ("missing_artifact_manifest_digest_record",),
        )
    if not _well_formed_digest(artifact.manifest_digest):
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_artifact_manifest_digest",),
        )
    if artifact.model_layer_digest is None:
        return _reject(
            model_name,
            registry_identity_value,
            ("missing_artifact_layer_digest_record",),
        )
    if not _well_formed_digest(artifact.model_layer_digest):
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_artifact_layer_digest",),
        )

    records = list(evidence_records)
    if not records:
        return _reject(
            model_name,
            registry_identity_value,
            ("missing_evidence",),
        )

    for record in records:
        if not isinstance(record, OriginEvidenceRecord):
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_evidence_record",),
            )
        # Independently verifiable evidence must come from the single
        # pull-time manifest record source. Model names, URLs, and any other
        # identifier are never acceptable evidence sources.
        if record.source != LOCAL_EVIDENCE_SOURCE:
            return _reject(
                model_name,
                registry_identity_value,
                ("unsupported_evidence_source",),
            )
        if not _well_formed_digest(record.manifest_digest):
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_evidence_manifest_digest",),
            )
        if not _well_formed_digest(record.model_layer_digest):
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_evidence_layer_digest",),
            )
        if _registry_identity_parts(record.registry_identity) is None:
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_evidence_registry_identity",),
            )
        if record.captured_at is not None and (
            isinstance(record.captured_at, bool)
            or not isinstance(record.captured_at, (int, float))
        ):
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_evidence_timestamp",),
            )
        if record.upstream_origin is not None and (
            not isinstance(record.upstream_origin, str)
            or not record.upstream_origin.strip()
        ):
            return _reject(
                model_name,
                registry_identity_value,
                ("malformed_upstream_origin_claim",),
            )

    # Ambiguous or conflicting evidence records cannot identify one artifact.
    consensus_keys = {
        (
            record.registry_identity,
            record.manifest_digest,
            record.model_layer_digest,
        )
        for record in records
    }
    if len(consensus_keys) != 1:
        return _reject(
            model_name,
            registry_identity_value,
            ("conflicting_evidence",),
        )
    evidence_registry, evidence_manifest_digest, evidence_layer_digest = (
        consensus_keys.pop()
    )
    if evidence_registry != registry_identity_value:
        return _reject(
            model_name,
            registry_identity_value,
            ("artifact_registry_identity_mismatch",),
        )
    if evidence_manifest_digest != artifact.manifest_digest:
        return _reject(
            model_name,
            registry_identity_value,
            ("artifact_manifest_digest_mismatch",),
        )
    if evidence_layer_digest != artifact.model_layer_digest:
        return _reject(
            model_name,
            registry_identity_value,
            ("artifact_layer_digest_mismatch",),
        )

    claims = {
        record.upstream_origin
        for record in records
        if record.upstream_origin is not None
    }
    if len(claims) > 1:
        return _reject(
            model_name,
            registry_identity_value,
            ("ambiguous_upstream_origin_claim",),
        )
    upstream_origin_claim = next(iter(claims)) if claims else None

    timestamps = [record.captured_at for record in records]
    if len({value for value in timestamps}) > 1:
        return _reject(
            model_name,
            registry_identity_value,
            ("inconsistent_evidence_timestamp",),
        )
    captured_at = timestamps[0]
    if captured_at is None:
        return _reject(
            model_name,
            registry_identity_value,
            ("no_evidence_timestamp",),
        )
    assert isinstance(captured_at, (int, float)) and not isinstance(
        captured_at,
        bool,
    )
    if captured_at > now:
        return _reject(
            model_name,
            registry_identity_value,
            ("future_evidence_timestamp",),
        )
    if now - captured_at > max_age_seconds:
        return _reject(
            model_name,
            registry_identity_value,
            ("stale_evidence",),
        )

    # Anchoring requires the small manifest file itself. Its content must
    # hash to the recorded digest; this is the only cryptographic check, and
    # it is real and locally completed here.
    if manifest_path is None:
        return _reject(
            model_name,
            registry_identity_value,
            ("manifest_file_unavailable",),
            upstream_origin_claim=upstream_origin_claim,
        )
    reader = manifest_reader or _default_manifest_reader
    try:
        data = reader(manifest_path)
    except (OSError, ValueError):
        return _reject(
            model_name,
            registry_identity_value,
            ("manifest_file_unreadable",),
            upstream_origin_claim=upstream_origin_claim,
        )
    if not isinstance(data, bytes):
        return _reject(
            model_name,
            registry_identity_value,
            ("manifest_file_unreadable",),
            upstream_origin_claim=upstream_origin_claim,
        )
    if len(data) > _MANIFEST_MAX_BYTES:
        return _reject(
            model_name,
            registry_identity_value,
            ("manifest_file_out_of_bounds",),
            upstream_origin_claim=upstream_origin_claim,
        )

    recorded_match = _DIGEST.fullmatch(evidence_manifest_digest)
    assert recorded_match is not None
    computed = hashlib.sha256(data).hexdigest()
    if computed != recorded_match.group(1):
        return _reject(
            model_name,
            registry_identity_value,
            ("manifest_content_mismatch",),
            upstream_origin_claim=upstream_origin_claim,
        )

    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError):
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_manifest_content",),
            upstream_origin_claim=upstream_origin_claim,
        )
    if not isinstance(manifest, dict):
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_manifest_content",),
            upstream_origin_claim=upstream_origin_claim,
        )
    layers = manifest.get("layers")
    if not isinstance(layers, list):
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_manifest_content",),
            upstream_origin_claim=upstream_origin_claim,
        )
    model_layers = [
        layer
        for layer in layers
        if isinstance(layer, dict)
        and layer.get("mediaType") == _MODEL_LAYER
    ]
    if len(model_layers) != 1:
        return _reject(
            model_name,
            registry_identity_value,
            ("malformed_manifest_content",),
            upstream_origin_claim=upstream_origin_claim,
        )
    chained_digest = model_layers[0].get("digest")
    if chained_digest != evidence_layer_digest:
        return _reject(
            model_name,
            registry_identity_value,
            ("layer_digest_chain_mismatch",),
            upstream_origin_claim=upstream_origin_claim,
        )

    # Anchored: the local manifest binding is verified. The result still
    # explicitly records what was NOT verified.
    return OriginEvidenceResult(
        model_name=model_name,
        registry_identity=registry_identity_value,
        status="anchored",
        reasons=_ANCHORED_REASONS,
        verified_manifest_digest=evidence_manifest_digest,
        model_layer_digest=evidence_layer_digest,
        upstream_origin_claim=upstream_origin_claim,
        upstream_origin_verified=False,
        trust_root=trust_root,
    )