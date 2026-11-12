"""Synthetic-only artifact-bound task evidence association (M10B Phase 2E).

This module is intentionally pure and fail-closed. It consumes an already
computed M09B ``UpstreamBindingResult`` plus revision-bound provider evidence.
It performs no hashing, filesystem access, network access, model execution, or
recommendation mutation.

An ``associated`` result means only that provider-reported task metadata can be
tied to the exact upstream file bound to one local artifact at one immutable
revision. It does not verify task quality, performance, authorship, lineage, or
hardware suitability, and it does not promote recommendations.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal, Sequence

from .model_origin_evidence import (
    LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
    OriginEvidenceResult,
)
from .upstream_identity_binding import (
    UPSTREAM_FILE_DIGEST_TRUST_ROOT,
    UpstreamBindingResult,
)


ArtifactTaskAssociationStatus = Literal["associated", "unknown", "rejected"]
TaskApplicability = Literal["artifact_file", "repository", "unknown"]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}/[A-Za-z0-9._-]{1,150}$")
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._+-]+$")
_TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


@dataclass(frozen=True)
class LocalArtifactTaskContext:
    """Exact local Ollama artifact identity supplied by the caller."""

    model_id: str
    artifact_id: str
    registry_identity: str
    manifest_digest: str


@dataclass(frozen=True)
class RevisionBoundFileEvidence:
    """Provider file evidence tied to one immutable upstream revision."""

    repo_id: str
    revision: str
    file_name: str
    sha256_hex: str
    size_bytes: int
    source: str


@dataclass(frozen=True)
class ProviderTaskEvidence:
    """Provider-reported task metadata tied to an immutable revision."""

    repo_id: str
    revision: str
    task: str
    source: str
    applicability: TaskApplicability
    file_name: str | None = None


@dataclass(frozen=True)
class ArtifactTaskAssociationResult:
    """Fail-closed association result. No recommendation authority is implied."""

    status: ArtifactTaskAssociationStatus
    reasons: tuple[str, ...]
    model_id: str | None = None
    artifact_id: str | None = None
    registry_identity: str | None = None
    task: str | None = None
    repo_id: str | None = None
    revision: str | None = None
    file_name: str | None = None
    task_sources: tuple[str, ...] = ()
    binding_trust_root: str | None = None
    task_performance_verified: bool = False
    recommendation_promoted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def _safe_text(value: object, *, max_length: int = 512) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= max_length
        and not _has_control_characters(value)
        and "\x00" not in value
    )


def _opaque_id_is_safe(value: object) -> bool:
    if not _safe_text(value):
        return False
    assert isinstance(value, str)
    return not value.startswith(("/", "\\", ".")) and "\\" not in value


def _registry_identity_is_safe(value: object) -> bool:
    if not _safe_text(value):
        return False
    assert isinstance(value, str)
    parts = value.split("/")
    return (
        len(parts) >= 2
        and all(
            part not in (".", "..")
            and _SAFE_COMPONENT_RE.fullmatch(part) is not None
            for part in parts
        )
    )


def _repo_id_is_safe(value: object) -> bool:
    if not isinstance(value, str) or _REPO_ID_RE.fullmatch(value) is None:
        return False
    return all(part not in (".", "..") for part in value.split("/"))


def _file_name_is_safe(value: object) -> bool:
    if not _safe_text(value, max_length=1024):
        return False
    assert isinstance(value, str)
    if value.startswith(("/", "\\")) or "\\" in value:
        return False
    parts = value.split("/")
    return bool(parts) and all(
        part not in (".", "..")
        and _SAFE_COMPONENT_RE.fullmatch(part) is not None
        for part in parts
    )


def _source_is_safe(value: object) -> bool:
    if not _safe_text(value, max_length=1024):
        return False
    assert isinstance(value, str)
    return not value.startswith(("/", "\\", ".")) and "\\" not in value


def _finish(
    status: ArtifactTaskAssociationStatus,
    reasons: tuple[str, ...],
    *,
    context: LocalArtifactTaskContext | None = None,
    task: str | None = None,
    repo_id: str | None = None,
    revision: str | None = None,
    file_name: str | None = None,
    task_sources: tuple[str, ...] = (),
    binding_trust_root: str | None = None,
) -> ArtifactTaskAssociationResult:
    safe_context = (
        context
        if isinstance(context, LocalArtifactTaskContext)
        and _opaque_id_is_safe(context.model_id)
        and _opaque_id_is_safe(context.artifact_id)
        and _registry_identity_is_safe(context.registry_identity)
        else None
    )
    return ArtifactTaskAssociationResult(
        status=status,
        reasons=tuple(dict.fromkeys((*reasons, "task_performance_not_verified", "recommendation_not_promoted"))),
        model_id=safe_context.model_id if safe_context is not None else None,
        artifact_id=safe_context.artifact_id if safe_context is not None else None,
        registry_identity=(
            safe_context.registry_identity if safe_context is not None else None
        ),
        task=task if isinstance(task, str) and _TASK_RE.fullmatch(task) else None,
        repo_id=repo_id if _repo_id_is_safe(repo_id) else None,
        revision=revision if isinstance(revision, str) and _REVISION_RE.fullmatch(revision) else None,
        file_name=file_name if _file_name_is_safe(file_name) else None,
        task_sources=tuple(
            source for source in task_sources if _source_is_safe(source)
        ),
        binding_trust_root=(
            binding_trust_root
            if binding_trust_root == UPSTREAM_FILE_DIGEST_TRUST_ROOT
            else None
        ),
        task_performance_verified=False,
        recommendation_promoted=False,
    )


def _validate_context(context: object) -> bool:
    return (
        isinstance(context, LocalArtifactTaskContext)
        and _opaque_id_is_safe(context.model_id)
        and _opaque_id_is_safe(context.artifact_id)
        and _registry_identity_is_safe(context.registry_identity)
        and isinstance(context.manifest_digest, str)
        and context.manifest_digest.startswith("sha256:")
        and _SHA256_RE.fullmatch(context.manifest_digest[7:]) is not None
    )


def _validate_revision_file(record: object) -> bool:
    return (
        isinstance(record, RevisionBoundFileEvidence)
        and _repo_id_is_safe(record.repo_id)
        and isinstance(record.revision, str)
        and _REVISION_RE.fullmatch(record.revision) is not None
        and _file_name_is_safe(record.file_name)
        and isinstance(record.sha256_hex, str)
        and _SHA256_RE.fullmatch(record.sha256_hex) is not None
        and not isinstance(record.size_bytes, bool)
        and isinstance(record.size_bytes, int)
        and record.size_bytes >= 0
        and _source_is_safe(record.source)
    )


def _validate_task_record(record: object) -> bool:
    return (
        isinstance(record, ProviderTaskEvidence)
        and _repo_id_is_safe(record.repo_id)
        and isinstance(record.revision, str)
        and _REVISION_RE.fullmatch(record.revision) is not None
        and isinstance(record.task, str)
        and _TASK_RE.fullmatch(record.task) is not None
        and _source_is_safe(record.source)
        and record.applicability in {"artifact_file", "repository", "unknown"}
        and (
            record.file_name is None
            or _file_name_is_safe(record.file_name)
        )
    )


def associate_artifact_task_evidence(
    *,
    context: LocalArtifactTaskContext,
    origin: OriginEvidenceResult,
    binding: UpstreamBindingResult,
    task: str,
    revision_files: Sequence[RevisionBoundFileEvidence] = (),
    task_records: Sequence[ProviderTaskEvidence] = (),
) -> ArtifactTaskAssociationResult:
    """Associate one reported task with one exactly bound local artifact.

    This validator is synthetic-input only in M10B Phase 2E. Callers must
    provide revision-bound file and task records explicitly. The function
    performs no I/O and never mutates model metadata or recommendation state.
    """

    if not _validate_context(context):
        return _finish("rejected", ("malformed_local_artifact_context",))

    if not isinstance(task, str) or _TASK_RE.fullmatch(task) is None:
        return _finish(
            "rejected",
            ("malformed_task",),
            context=context,
        )

    expected_artifact_id = f"{context.model_id}:artifact"
    if context.artifact_id != expected_artifact_id:
        return _finish(
            "rejected",
            ("local_artifact_id_mismatch",),
            context=context,
            task=task,
        )

    if not isinstance(origin, OriginEvidenceResult):
        return _finish(
            "rejected",
            ("malformed_local_origin_evidence",),
            context=context,
            task=task,
        )

    if origin.status != "anchored":
        return _finish(
            "rejected",
            ("local_origin_not_anchored",),
            context=context,
            task=task,
        )

    expected_model_name = (
        context.model_id[len("ollama:"):]
        if context.model_id.startswith("ollama:")
        else None
    )
    if (
        expected_model_name is None
        or origin.model_name != expected_model_name
        or origin.registry_identity != context.registry_identity
        or origin.verified_manifest_digest != context.manifest_digest
        or origin.trust_root != LOCAL_MANIFEST_DIGEST_TRUST_ROOT
    ):
        return _finish(
            "rejected",
            ("local_origin_context_mismatch",),
            context=context,
            task=task,
        )

    if not isinstance(binding, UpstreamBindingResult):
        return _finish(
            "rejected",
            ("malformed_upstream_binding",),
            context=context,
            task=task,
        )

    if binding.status == "unknown":
        return _finish(
            "unknown",
            ("upstream_binding_unknown",),
            context=context,
            task=task,
        )
    if binding.status == "unbound":
        return _finish(
            "rejected",
            ("upstream_binding_unbound",),
            context=context,
            task=task,
        )
    if binding.status != "bound":
        return _finish(
            "rejected",
            ("malformed_upstream_binding_status",),
            context=context,
            task=task,
        )

    if (
        not _repo_id_is_safe(binding.matched_repo_id)
        or not _file_name_is_safe(binding.matched_file_name)
        or not isinstance(binding.matched_sha256, str)
        or _SHA256_RE.fullmatch(binding.matched_sha256) is None
        or not isinstance(binding.computed_blob_sha256, str)
        or binding.computed_blob_sha256 != binding.matched_sha256
        or isinstance(binding.local_blob_size, bool)
        or not isinstance(binding.local_blob_size, int)
        or binding.local_blob_size < 0
        or binding.trust_root != UPSTREAM_FILE_DIGEST_TRUST_ROOT
    ):
        return _finish(
            "rejected",
            ("malformed_bound_identity_evidence",),
            context=context,
            task=task,
        )

    expected_layer_digest = "sha256:" + binding.computed_blob_sha256
    if origin.model_layer_digest != expected_layer_digest:
        return _finish(
            "rejected",
            ("local_origin_blob_digest_mismatch",),
            context=context,
            task=task,
            binding_trust_root=binding.trust_root,
        )

    repo_id = binding.matched_repo_id
    file_name = binding.matched_file_name
    assert isinstance(repo_id, str)
    assert isinstance(file_name, str)
    assert isinstance(binding.matched_sha256, str)
    assert isinstance(binding.local_blob_size, int)

    files = tuple(revision_files)
    if not files:
        return _finish(
            "unknown",
            ("revision_bound_file_evidence_missing",),
            context=context,
            task=task,
            repo_id=repo_id,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )
    if any(not _validate_revision_file(record) for record in files):
        return _finish(
            "rejected",
            ("malformed_revision_bound_file_evidence",),
            context=context,
            task=task,
            repo_id=repo_id,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    file_keys = {
        (
            record.repo_id,
            record.revision,
            record.file_name,
            record.sha256_hex,
            record.size_bytes,
        )
        for record in files
    }
    if len(file_keys) != 1:
        return _finish(
            "rejected",
            ("conflicting_revision_bound_file_evidence",),
            context=context,
            task=task,
            repo_id=repo_id,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    (
        evidence_repo,
        revision,
        evidence_file,
        evidence_sha,
        evidence_size,
    ) = next(iter(file_keys))

    if evidence_repo != repo_id:
        return _finish(
            "rejected",
            ("revision_file_repo_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )
    if evidence_file != file_name:
        return _finish(
            "rejected",
            ("revision_file_name_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )
    if evidence_sha != binding.matched_sha256:
        return _finish(
            "rejected",
            ("revision_file_digest_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )
    if evidence_size != binding.local_blob_size:
        return _finish(
            "rejected",
            ("revision_file_size_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    records = tuple(task_records)
    if any(not _validate_task_record(record) for record in records):
        return _finish(
            "rejected",
            ("malformed_provider_task_evidence",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    matching = tuple(record for record in records if record.task == task)
    if not matching:
        return _finish(
            "unknown",
            ("provider_task_evidence_missing",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    applicability_keys = {
        (record.repo_id, record.revision, record.applicability, record.file_name)
        for record in matching
    }
    if len(applicability_keys) != 1:
        return _finish(
            "rejected",
            ("conflicting_provider_task_evidence",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            binding_trust_root=binding.trust_root,
        )

    task_repo, task_revision, applicability, task_file = next(iter(applicability_keys))
    task_sources = tuple(dict.fromkeys(record.source for record in matching))

    if task_repo != repo_id:
        return _finish(
            "rejected",
            ("task_repo_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            task_sources=task_sources,
            binding_trust_root=binding.trust_root,
        )
    if task_revision != revision:
        return _finish(
            "rejected",
            ("task_revision_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            task_sources=task_sources,
            binding_trust_root=binding.trust_root,
        )
    if applicability != "artifact_file":
        return _finish(
            "unknown",
            ("task_applicability_not_artifact_scoped",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            task_sources=task_sources,
            binding_trust_root=binding.trust_root,
        )
    if task_file != file_name:
        return _finish(
            "rejected",
            ("task_file_mismatch",),
            context=context,
            task=task,
            repo_id=repo_id,
            revision=revision,
            file_name=file_name,
            task_sources=task_sources,
            binding_trust_root=binding.trust_root,
        )

    return _finish(
        "associated",
        (
            "exact_upstream_file_binding",
            "revision_bound_file_match",
            "artifact_scoped_task_metadata",
        ),
        context=context,
        task=task,
        repo_id=repo_id,
        revision=revision,
        file_name=file_name,
        task_sources=task_sources,
        binding_trust_root=binding.trust_root,
    )
