"""M10B Phase 2F: Immutable-revision upstream evidence producer (synthetic-only).

This module resolves a Hugging Face repository to an immutable git commit SHA
and fetches file identity and task metadata at that exact pinned revision.

Scope
-----
Produces structured evidence records that can be supplied to the Phase 2E
artifact-task evidence validator (``artifact_task_evidence.py``) once a caller
has also established M09A and M09B bindings.

What this module deliberately does NOT do
-----------------------------------------
- Task applicability is always ``"repository"`` for HF pipeline_tag metadata.
  HF ``pipeline_tag`` is a repository-level attribute. This module never
  converts repository-level labels into artifact-file evidence. That means
  ordinary HF pipeline_tag evidence will produce ``status="unknown"`` from
  the Phase 2E validator (reason ``task_applicability_not_artifact_scoped``),
  not ``"associated"``. Artifact-file applicability requires separate explicit
  provider evidence that is not available from the standard HF API; that is a
  future concern.
- No existing M09B contracts (``UpstreamFileRecord``, ``UpstreamFetchResult``,
  ``fetch_upstream_file_records``, ``UpstreamNetworkGate``) are changed.
- No existing ``ModelProfile``, ``ModelIdentity``, recommendation, or dashboard
  behavior is changed.
- No implicit network requests: every request requires an explicit gate.
- No model file hashing, model execution, GPU allocation, or WorkRunner
  delegation.

Network pattern
---------------
Two bounded sequential HTTP calls, both guarded by an explicit
``RevisionNetworkGate``. Neither call is made without the gate.

Call 1 -- Repository info:
  ``GET https://huggingface.co/api/models/{repo_id}``
  Extracts: ``sha`` (immutable 40-64 char hex commit SHA), ``pipeline_tag``

Call 2 -- Revision-pinned file tree:
  ``GET https://huggingface.co/api/models/{repo_id}/tree/{sha}``
  Extracts: file names, LFS sha256 digests, file sizes

Both calls refuse redirects, block proxies, enforce a hard response-size cap,
and use the same timeout as M09B. Injected fetcher parameters make all tests
synthetic with zero live network calls.

Result contract
---------------
``RevisionTaskRecord`` entries always carry ``applicability="repository"``.
Callers must not assume artifact-file task applicability from this module.
Callers that supply ``RevisionTaskRecord``-derived ``ProviderTaskEvidence``
to the Phase 2E validator will receive ``status="unknown"`` for tasks, not
``"associated"``, because ``applicability != "artifact_file"``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

if TYPE_CHECKING:
    from .artifact_task_evidence import (
        ProviderTaskEvidence,
        RevisionBoundFileEvidence,
    )


# ---------------------------------------------------------------------------
# URL templates
# ---------------------------------------------------------------------------

_REPO_INFO_URL = "https://huggingface.co/api/models/{repo_id}"
_REVISION_TREE_URL = "https://huggingface.co/api/models/{repo_id}/tree/{revision}"

# ---------------------------------------------------------------------------
# Network bounds (same values as M09B, not owner-tunable)
# ---------------------------------------------------------------------------

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_RECORDS = 512
_TIMEOUT_SECONDS = 10.0

# ---------------------------------------------------------------------------
# Source / provenance constants
# ---------------------------------------------------------------------------

REVISION_EVIDENCE_SOURCE = "huggingface-revision-bound-file-digest"
REVISION_TASK_SOURCE = "huggingface-revision-pipeline-tag"

# ---------------------------------------------------------------------------
# Validation patterns
# ---------------------------------------------------------------------------

_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}/[A-Za-z0-9._-]{1,150}$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40,64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9._+-]+$")
_TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


# ---------------------------------------------------------------------------
# Gate and authorization
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RevisionNetworkGate:
    """Explicit authorization to fetch revision evidence for one repository.

    ``allow_network`` must be ``True`` and ``repo_id`` must match the
    target repository exactly. No request is ever made without this gate.
    """

    allow_network: bool
    repo_id: str


class RevisionNetworkNotAuthorized(RuntimeError):
    """Raised when revision evidence retrieval is attempted without an explicit
    gate or when the gate does not cover the requested repo. No request is
    made in that case.
    """


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RevisionFileRecord:
    """One file record at an immutable repository revision.

    ``sha256_hex`` and ``size_bytes`` come from the LFS metadata in the tree
    response. Either may be ``None`` when the provider does not publish them.
    Non-LFS files have no ``sha256_hex``.
    """

    repo_id: str
    revision: str
    file_name: str
    sha256_hex: str | None
    size_bytes: int | None
    source: str = REVISION_EVIDENCE_SOURCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionTaskRecord:
    """Provider-reported task metadata at an immutable repository revision.

    ``applicability`` is always ``"repository"`` because HF ``pipeline_tag``
    is a repository-level attribute. This record never provides artifact-file
    evidence. Callers that supply this (via ``to_provider_task_evidence``) to
    the Phase 2E validator will receive ``status="unknown"`` with reason
    ``task_applicability_not_artifact_scoped``.
    """

    repo_id: str
    revision: str
    task: str
    applicability: Literal["repository"] = "repository"
    source: str = REVISION_TASK_SOURCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionEvidenceFail:
    """One bounded, deterministic, privacy-safe evidence failure.

    ``reason`` is a machine code; it never contains paths, digests,
    credentials, or other potentially private material.
    """

    repo_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionEvidenceResult:
    """Combined result from one two-call bounded revision evidence fetch.

    ``revision`` is ``None`` when the info call failed or produced no valid
    immutable SHA. ``file_records`` is empty when the tree call failed or
    returned no parseable entries. ``task_records`` is empty when
    ``pipeline_tag`` was absent or malformed.

    All ``RevisionTaskRecord`` entries carry ``applicability="repository"``.
    Callers must not assume artifact-file task applicability from this result.
    """

    repo_id: str
    revision: str | None
    file_records: tuple[RevisionFileRecord, ...]
    task_records: tuple[RevisionTaskRecord, ...]
    failures: tuple[RevisionEvidenceFail, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "revision": self.revision,
            "file_records": [r.to_dict() for r in self.file_records],
            "task_records": [t.to_dict() for t in self.task_records],
            "failures": [f.to_dict() for f in self.failures],
        }


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _repo_id_is_well_formed(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if _REPO_ID_RE.fullmatch(value) is None:
        return False
    return all(part not in (".", "..") for part in value.split("/"))


def _revision_is_immutable(value: object) -> bool:
    """An immutable revision must be a 40-64 character lowercase hex string.

    Branch or tag labels (``main``, ``master``, ``HEAD``, ``v1.0``, etc.)
    are not hex and are always rejected. Only commit SHAs are accepted.
    """
    return isinstance(value, str) and _REVISION_RE.fullmatch(value) is not None


def _file_name_is_safe(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or "\x00" in value:
        return False
    parts = value.split("/")
    if not parts or any(not part for part in parts):
        return False
    return all(
        part not in (".", "..")
        and _SAFE_PATH_COMPONENT_RE.fullmatch(part) is not None
        for part in parts
    )


def _normalize_sha256(value: object) -> str | None:
    """Normalize a provider-published LFS oid to bare 64-char hex.

    Accepts bare 64-char hex only. Rejects everything else.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if _SHA256_RE.fullmatch(stripped) is not None:
        return stripped
    return None


def _normalize_pipeline_tag(value: object) -> str | None:
    """Accept a pipeline_tag that is a safe, non-empty task string.

    Returns ``None`` for absent, empty, or malformed values. No exception.
    """
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if _TASK_RE.fullmatch(stripped) is not None:
        return stripped
    return None


# ---------------------------------------------------------------------------
# HTTP helpers (same safety patterns as M09B)
# ---------------------------------------------------------------------------


class _NoRedirects(HTTPRedirectHandler):
    """Refuse all redirects. Revision evidence requests are bounded to exact
    URLs; following a redirect could bypass the pinned revision.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise HTTPError(newurl, code, "redirect refused", headers, fp)


def _bounded_get(url: str) -> bytes:
    """Single exact-URL GET with no proxies, no redirects, hard size cap."""
    request = Request(url, headers={"Accept": "application/json"})
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
        return response.read(_MAX_RESPONSE_BYTES + 1)


def _default_info_fetcher(repo_id: str) -> bytes:
    """Fetch repository info for one explicitly supplied repo."""
    return _bounded_get(_REPO_INFO_URL.format(repo_id=repo_id))


def _default_tree_fetcher(repo_id: str, revision: str) -> bytes:
    """Fetch revision-pinned file tree for one explicitly supplied repo.

    The ``revision`` parameter is a validated immutable SHA; it is never
    a floating branch label.
    """
    return _bounded_get(
        _REVISION_TREE_URL.format(repo_id=repo_id, revision=revision)
    )


# ---------------------------------------------------------------------------
# Tree entry parsing
# ---------------------------------------------------------------------------


def _parse_tree_entry(
    repo_id: str,
    revision: str,
    entry: object,
) -> RevisionFileRecord | None:
    """Parse one file entry from a revision-pinned HF tree response."""
    if not isinstance(entry, dict):
        return None
    if entry.get("type") != "file":
        return None

    path = entry.get("path")
    if not _file_name_is_safe(path):
        return None

    size = entry.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        size_bytes: int | None = None
    else:
        size_bytes = size

    lfs = entry.get("lfs")
    sha256_hex: str | None = None
    if isinstance(lfs, dict):
        sha256_hex = _normalize_sha256(lfs.get("oid"))

    assert isinstance(path, str)
    return RevisionFileRecord(
        repo_id=repo_id,
        revision=revision,
        file_name=path,
        sha256_hex=sha256_hex,
        size_bytes=size_bytes,
    )


# ---------------------------------------------------------------------------
# Main producer function
# ---------------------------------------------------------------------------


def fetch_revision_evidence(
    repo_id: str,
    *,
    gate: RevisionNetworkGate | None,
    info_fetcher: Callable[[str], bytes] | None = None,
    tree_fetcher: Callable[[str, str], bytes] | None = None,
) -> RevisionEvidenceResult:
    """Fetch file and task evidence at an immutable revision for one repo.

    Two-step bounded process:

    1. Fetch repository info -> extract immutable commit SHA and pipeline_tag.
    2. Fetch file tree at that exact SHA -> extract file records.

    Task applicability is always ``"repository"``. This function never
    converts HF pipeline_tag into artifact-file evidence.

    Requires an explicit ``RevisionNetworkGate``; raises
    ``RevisionNetworkNotAuthorized`` without making any request when the
    gate is absent, does not allow network access, or does not cover this
    ``repo_id``.

    Both fetchers may be replaced via injection for synthetic testing; the
    defaults perform live HTTP calls and must not be used in tests.
    """

    def _fail(reason: str) -> RevisionEvidenceResult:
        safe_repo = repo_id if isinstance(repo_id, str) else ""
        return RevisionEvidenceResult(
            repo_id=safe_repo,
            revision=None,
            file_records=(),
            task_records=(),
            failures=(RevisionEvidenceFail(repo_id=safe_repo, reason=reason),),
        )

    def _partial_fail(rev: str, reason: str) -> RevisionEvidenceResult:
        return RevisionEvidenceResult(
            repo_id=repo_id,
            revision=rev,
            file_records=(),
            task_records=(),
            failures=(RevisionEvidenceFail(repo_id=repo_id, reason=reason),),
        )

    if not _repo_id_is_well_formed(repo_id):
        return _fail("malformed_repo_id")

    # Gate check -- no request is ever made without explicit authorization.
    if not isinstance(gate, RevisionNetworkGate) or not gate.allow_network:
        raise RevisionNetworkNotAuthorized(
            "revision evidence retrieval requires an explicit gate"
        )
    if gate.repo_id != repo_id:
        raise RevisionNetworkNotAuthorized(
            "repository not covered by the explicit gate"
        )

    # --- Call 1: Repository info (SHA + pipeline_tag) ---
    resolved_info_fetcher = info_fetcher or _default_info_fetcher

    try:
        info_payload = resolved_info_fetcher(repo_id)
    except (OSError, URLError, ValueError):
        return _fail("info_network_failure")

    if len(info_payload) > _MAX_RESPONSE_BYTES:
        return _fail("info_response_too_large")

    try:
        info_decoded = json.loads(info_payload.decode("utf-8"))
    except (UnicodeError, ValueError):
        return _fail("info_response_malformed")

    if not isinstance(info_decoded, dict):
        return _fail("info_response_not_object")

    sha_raw = info_decoded.get("sha")
    if sha_raw is None:
        return _fail("revision_sha_missing")

    if not _revision_is_immutable(sha_raw):
        return _fail("revision_sha_not_immutable")

    revision: str = sha_raw  # Confirmed: 40-64 char hex; immutable.

    pipeline_tag = _normalize_pipeline_tag(info_decoded.get("pipeline_tag"))

    # --- Call 2: Revision-pinned file tree ---
    resolved_tree_fetcher = tree_fetcher or _default_tree_fetcher

    try:
        tree_payload = resolved_tree_fetcher(repo_id, revision)
    except (OSError, URLError, ValueError):
        return _partial_fail(revision, "tree_network_failure")

    if len(tree_payload) > _MAX_RESPONSE_BYTES:
        return _partial_fail(revision, "tree_response_too_large")

    try:
        tree_decoded = json.loads(tree_payload.decode("utf-8"))
    except (UnicodeError, ValueError):
        return _partial_fail(revision, "tree_response_malformed")

    if not isinstance(tree_decoded, list):
        return _partial_fail(revision, "tree_response_not_array")

    if len(tree_decoded) > _MAX_RECORDS:
        return _partial_fail(revision, "tree_records_limit_exceeded")

    file_records: list[RevisionFileRecord] = []
    for entry in tree_decoded:
        record = _parse_tree_entry(repo_id, revision, entry)
        if record is not None:
            file_records.append(record)

    task_records: list[RevisionTaskRecord] = []
    if pipeline_tag is not None:
        task_records.append(
            RevisionTaskRecord(
                repo_id=repo_id,
                revision=revision,
                task=pipeline_tag,
                applicability="repository",
            )
        )

    return RevisionEvidenceResult(
        repo_id=repo_id,
        revision=revision,
        file_records=tuple(file_records),
        task_records=tuple(task_records),
        failures=(),
    )


# ---------------------------------------------------------------------------
# Phase 2E conversion helpers
# ---------------------------------------------------------------------------


def to_revision_bound_file_evidence(
    record: RevisionFileRecord,
) -> "RevisionBoundFileEvidence | None":
    """Convert a ``RevisionFileRecord`` to Phase 2E's ``RevisionBoundFileEvidence``.

    Returns ``None`` when ``sha256_hex`` or ``size_bytes`` is ``None``
    (non-LFS files or missing provider data), because
    ``RevisionBoundFileEvidence`` requires both as non-optional fields.
    """
    from .artifact_task_evidence import RevisionBoundFileEvidence

    if record.sha256_hex is None or record.size_bytes is None:
        return None

    return RevisionBoundFileEvidence(
        repo_id=record.repo_id,
        revision=record.revision,
        file_name=record.file_name,
        sha256_hex=record.sha256_hex,
        size_bytes=record.size_bytes,
        source=record.source,
    )


def to_provider_task_evidence(
    record: RevisionTaskRecord,
) -> "ProviderTaskEvidence":
    """Convert a ``RevisionTaskRecord`` to Phase 2E's ``ProviderTaskEvidence``.

    The resulting ``ProviderTaskEvidence`` has ``applicability="repository"``
    and ``file_name=None``. When supplied to the Phase 2E validator
    (``associate_artifact_task_evidence``), the validator will return
    ``status="unknown"`` with reason ``task_applicability_not_artifact_scoped``
    because ``applicability != "artifact_file"``. This is correct and
    expected behavior: HF pipeline_tag is repository-level evidence.
    """
    from .artifact_task_evidence import ProviderTaskEvidence

    return ProviderTaskEvidence(
        repo_id=record.repo_id,
        revision=record.revision,
        task=record.task,
        source=record.source,
        applicability=record.applicability,
        file_name=None,
    )
