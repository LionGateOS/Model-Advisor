"""M09B identity-evidence foundation (V1): upstream identity binding.

Scope of this milestone (M09B)
------------------------------
An evidence and identity-verification foundation only. This module adds:

1. Claim extraction for GGUF identity metadata (``general.basename``,
   ``general.repo_url``, ``general.quantized_by``,
   ``general.base_model.N.repo_url``) and for local manifest ``from``
   labels. Every extracted value is an UNVERIFIED claim, never proof.
2. Local model-layer digest groups: registrations that share one locally
   declared model-layer digest are connected as local byte-identity
   evidence. That is a LOCAL finding only and is never promoted into
   upstream identity proof.
3. Explicitly gated full-blob SHA-256 hashing of one selected local
   artifact. Hashing never runs by default: it requires an explicit
   plan plus an explicit authorization acknowledging the disclosed file
   size and read cost beforehand. Default behavior never hashes large
   model files.
4. Bounded upstream evidence retrieval restricted to explicitly supplied
   Hugging Face candidate repositories (fixed caps on request count,
   response size, timeout, redirects, and record count). No candidate is
   ever discovered by filename similarity; requests are bounded to the
   explicitly supplied repos.
5. A fail-closed, deterministic binding validator that accepts an
   upstream byte-identity binding ONLY when the locally computed SHA-256
   of the selected blob equals an independently retrieved provider-
   published SHA-256 digest for an exact upstream file, with a unique
   unambiguous match and consistent file size where available.

What V1 deliberately does NOT claim
------------------------------------
- Owner mappings and GGUF header URLs may PROPOSE candidates; they can
  never establish verified origin.
- A matching manifest-declared local layer digest is NOT equivalent to
  recomputing the local blob hash; the two are kept distinct and any
  mismatch is reported.
- Provider digest records are evidence of byte identity to a hosted
  upstream file. They are NOT proof of original authorship, safety,
  licensing, model suitability, or lineage.
- No workload recommendation promotion: nothing in this module feeds the
  recommendation layer, which stays ``workload_unknown`` without
  separately authorized evidence changes.
- This job did not execute live hashing or network verification; both
  remain explicit, disclosed, gated operations.

Result contract
---------------
Binding results are ``bound``, ``unbound``, or ``unknown``. Missing,
malformed, conflicting, or ambiguous evidence fails closed (never
``bound``). Reason strings are deterministic machine codes and never
contain local filesystem paths, timestamps, evidence values, credentials,
or other potentially private material: malformed or private-path claims
are recorded by reason code with their values withheld.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .ollama_manifest_identity import (
    ManifestLayerRecord,
    _DIGEST,
    _is_safe_component,
    collect_manifest_layer_records,
)
from .model_origin_evidence import _registry_identity_parts


UPSTREAM_FILE_DIGEST_TRUST_ROOT = "huggingface-provider-published-file-digest"

UPSTREAM_EVIDENCE_SOURCE = "huggingface-provider-published-digest"

PROPOSAL_SOURCE_OWNER_MAPPING = "owner-mapping-explicit"

PROPOSAL_SOURCE_GGUF_HEADER = "gguf-header-claim"

# Upstream network bounds (fixed, not owner-tunable, to prevent weakening).
UPSTREAM_MAX_CANDIDATE_REPOS = 4
_UPSTREAM_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_UPSTREAM_MAX_RECORDS = 512
_UPSTREAM_TIMEOUT_SECONDS = 10.0

_UPSTREAM_TREE_URL = "https://huggingface.co/api/models/{repo_id}/tree/main"

# Local blob hashing reads in fixed chunks; the plan discloses the size.
_LOCAL_BLOB_HASH_CHUNK_BYTES = 1024 * 1024

UpstreamBindingStatus = Literal["bound", "unbound", "unknown"]

_BLOB_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}/[A-Za-z0-9._-]{1,150}$")

_BASE_MODEL_REPO_URL_RE = re.compile(r"^general\.base_model(?:\.(\d+))?\.repo_url$")

_HUGGINGFACE_HOSTS = frozenset({"huggingface.co", "www.huggingface.co"})

_BASE_NONVERIFICATION_REASONS = (
    "upstream_authorship_not_verified",
    "lineage_not_verified",
    "workload_suitability_not_assessed",
)


# ---------------------------------------------------------------------------
# Phase 1 — GGUF identity claim extraction (unverified claims only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnverifiedIdentityClaim:
    """One extracted GGUF identity claim.

    ``value`` is withheld (``None``) whenever the claim is malformed or
    looks like a private/local path; only the deterministic reason code
    survives, never the raw value. Every claim, well-formed or not, is
    unverified.
    """

    field: str
    kind: Literal["basename", "repo_url", "quantized_by"]
    value: str | None = None
    well_formed: bool = False
    note: str | None = None
    source_type: str = "gguf-header"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GGUFIdentityClaims:
    """Structured GGUF identity claims extracted from one metadata mapping."""

    basename: UnverifiedIdentityClaim | None = None
    repo_url: UnverifiedIdentityClaim | None = None
    quantized_by: UnverifiedIdentityClaim | None = None
    base_model_repo_urls: tuple[UnverifiedIdentityClaim, ...] = ()

    @property
    def claims(self) -> tuple[UnverifiedIdentityClaim, ...]:
        specific = (
            item
            for item in (
                self.basename,
                self.repo_url,
                self.quantized_by,
            )
            if item is not None
        )
        return (*specific, *self.base_model_repo_urls)

    def to_dict(self) -> dict[str, Any]:
        return {
            "basename": (
                self.basename.to_dict() if self.basename is not None else None
            ),
            "repo_url": (
                self.repo_url.to_dict() if self.repo_url is not None else None
            ),
            "quantized_by": (
                self.quantized_by.to_dict()
                if self.quantized_by is not None
                else None
            ),
            "base_model_repo_urls": [
                item.to_dict() for item in self.base_model_repo_urls
            ],
            "all_unverified": True,
        }


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)


def _evaluate_string_claim(value: str) -> str | None:
    """Return a deterministic rejection note, or ``None`` when fine."""

    if not value or value != value.strip():
        return "claim_empty_or_untrimmed"
    if _has_control_characters(value) or "\x00" in value:
        return "claim_control_characters_rejected"
    if len(value) > 1024:
        return "claim_length_rejected"
    return None


def _evaluate_basename(value: object) -> tuple[str | None, str | None]:
    note = _evaluate_string_claim(value) if isinstance(value, str) else (
        "claim_not_string"
    )
    if note is not None:
        return None, note
    assert isinstance(value, str)
    if value.startswith("/") or value.startswith("\\") or ":" in value:
        return None, "claim_looks_like_path_rejected"
    if ".." in value or "/" in value or "\\" in value:
        return None, "claim_looks_like_path_rejected"
    return value, None


def _evaluate_quantized_by(value: object) -> tuple[str | None, str | None]:
    note = _evaluate_string_claim(value) if isinstance(value, str) else (
        "claim_not_string"
    )
    if note is not None:
        return None, note
    assert isinstance(value, str)
    if value.startswith("/") or value.startswith(".") or "\\" in value:
        return None, "claim_looks_like_path_rejected"
    return value, None


def _host_is_private(hostname: str) -> bool:
    lowered = hostname.casefold()
    if lowered in {"localhost", "::1"}:
        return True
    if lowered.startswith(("127.", "10.", "192.168.", "169.254.")):
        return True
    if re.match(r"^172\.(1[6-9]|2\d|3[01])\.", lowered):
        return True
    return False


def _evaluate_repo_url(value: object) -> tuple[str | None, str | None, str | None]:
    """Evaluate one repo URL claim.

    Returns ``(kept_value_or_None, note_or_None, host_or_None)``. Well
    formed https URLs without credentials, private hosts, or traversal
    components are preserved verbatim; everything else is withheld with a
    reason code.
    """

    if not isinstance(value, str):
        return None, "claim_not_string", None

    malformed_note = _evaluate_string_claim(value)
    if malformed_note is not None:
        return None, malformed_note, None

    try:
        parts = urlsplit(value)
    except ValueError:
        return None, "claim_not_parsable_url", None

    if parts.scheme != "https":
        return None, "claim_insecure_url_scheme", None
    netloc = parts.netloc.casefold()
    if "@" in netloc:
        return None, "claim_url_credential_material", None
    if not netloc:
        return None, "claim_url_without_host", None
    hostname = parts.hostname
    if not hostname:
        return None, "claim_url_without_host", None
    if _host_is_private(hostname):
        return None, "claim_private_host_rejected", hostname
    path_segments = [segment for segment in parts.path.split("/") if segment]
    if not path_segments:
        return None, "claim_looks_like_path_rejected", None
    if any(segment == ".." or segment == "." for segment in path_segments):
        return None, "claim_path_traversal_rejected", None
    return value, None, hostname


def extract_gguf_identity_claims(
    metadata: Mapping[str, Any],
) -> GGUFIdentityClaims:
    """Extract GGUF identity claims from a GGUF/Ollama ``model_info`` mapping.

    Reads only the documented identity keys. Every other key is ignored.
    All values are claims; malformed or path-like values are recorded by
    reason code with the raw value withheld. Never raises for missing or
    malformed claim values.
    """

    if not isinstance(metadata, Mapping):
        raise ValueError("GGUF identity claims require a metadata mapping")

    basename: UnverifiedIdentityClaim | None = None
    repo_url: UnverifiedIdentityClaim | None = None
    quantized_by: UnverifiedIdentityClaim | None = None
    base_model_repo_urls: list[UnverifiedIdentityClaim] = []

    def _claim(field: str, kind: str, raw: object) -> UnverifiedIdentityClaim:
        if kind == "basename":
            value, note = _evaluate_basename(raw)
        elif kind == "quantized_by":
            value, note = _evaluate_quantized_by(raw)
        else:
            value, note, _host = _evaluate_repo_url(raw)
        return UnverifiedIdentityClaim(
            field=field,
            kind=kind,
            value=value,
            well_formed=value is not None,
            note=note,
            source_type=PROPOSAL_SOURCE_GGUF_HEADER,
        )

    if "general.basename" in metadata:
        basename = _claim("general.basename", "basename", metadata["general.basename"])

    if "general.repo_url" in metadata:
        repo_url = _claim("general.repo_url", "repo_url", metadata["general.repo_url"])

    if "general.quantized_by" in metadata:
        quantized_by = _claim(
            "general.quantized_by", "quantized_by", metadata["general.quantized_by"]
        )

    for key in sorted(metadata, key=str):
        if not isinstance(key, str):
            continue
        base_match = _BASE_MODEL_REPO_URL_RE.fullmatch(key)
        if base_match is not None:
            base_model_repo_urls.append(
                _claim(key, "repo_url", metadata[key])
            )

    return GGUFIdentityClaims(
        basename=basename,
        repo_url=repo_url,
        quantized_by=quantized_by,
        base_model_repo_urls=tuple(base_model_repo_urls),
    )


# ---------------------------------------------------------------------------
# Candidate proposals (owner mappings and GGUF claims only, never proof)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OwnerUpstreamMapping:
    """One owner-provided candidate mapping (claim only, never proof)."""

    registry_identity: str
    repo_id: str
    file_name: str | None = None


@dataclass(frozen=True)
class UpstreamCandidate:
    """One explicitly proposed upstream candidate (claim only)."""

    repo_id: str
    file_name: str | None
    source: str


@dataclass(frozen=True)
class CandidateProposals:
    """Bounded candidate proposals plus deterministic decline notes."""

    candidates: tuple[UpstreamCandidate, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [
                {
                    "repo_id": item.repo_id,
                    "file_name": item.file_name,
                    "source": item.source,
                }
                for item in self.candidates
            ],
            "notes": list(self.notes),
        }


def _repo_id_is_well_formed(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if _REPO_ID_RE.fullmatch(value) is None:
        return False
    # Reject traversal components the character class alone permits.
    return all(part not in (".", "..") for part in value.split("/"))


def _file_name_is_well_formed(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or "\x00" in value:
        return False
    segments = value.split("/")
    if any(not segment for segment in segments):
        return False
    return all(_is_safe_component(segment) for segment in segments)


def _repo_id_from_huggingface_url(
    value: str,
) -> tuple[str, str | None] | None:
    parts = urlsplit(value)
    path_segments = [segment for segment in parts.path.split("/") if segment]
    if len(path_segments) < 2:
        return None

    file_name: str | None = None
    if len(path_segments) >= 5 and path_segments[2] == "resolve":
        file_parts = path_segments[4:]
        if file_parts and _file_name_is_well_formed("/".join(file_parts)):
            file_name = "/".join(file_parts)

    repo_id = "/".join(path_segments[:2])
    if not _repo_id_is_well_formed(repo_id):
        return None
    return repo_id, file_name


def propose_upstream_candidates(
    claims: GGUFIdentityClaims,
    owner_mappings: Sequence[OwnerUpstreamMapping] = (),
) -> CandidateProposals:
    """Build bounded candidate proposals from owner mappings and GGUF claims.

    Fail-closed rules:

    - No candidate is ever created from filename similarity or any search.
    - Only well-formed claims on a Hugging Face host propose candidates;
      well-formed claims on other hosts are declined with a note.
    - Malformed owner mappings are declined with a note.
    - If the unique candidate repository count exceeds the fixed cap, the
      whole proposal set is declined (never truncated).
    """

    notes: list[str] = []

    candidates: list[UpstreamCandidate] = []
    repos: set[str] = set()

    for mapping in owner_mappings:
        if (
            not isinstance(mapping, OwnerUpstreamMapping)
            or _registry_identity_parts(mapping.registry_identity) is None
            or not _repo_id_is_well_formed(mapping.repo_id)
            or (
                mapping.file_name is not None
                and not _file_name_is_well_formed(mapping.file_name)
            )
        ):
            notes.append("malformed_owner_mapping_ignored")
            continue

        candidate = UpstreamCandidate(
            repo_id=mapping.repo_id,
            file_name=mapping.file_name,
            source=PROPOSAL_SOURCE_OWNER_MAPPING,
        )
        candidates.append(candidate)
        repos.add(mapping.repo_id)

    claim_items = [item for item in claims.claims if item.kind == "repo_url"]
    for item in claim_items:
        if item.value is None or not item.well_formed:
            continue
        parsed = _repo_id_from_huggingface_url(item.value)
        if parsed is None:
            continue
        repo_id, file_name = parsed
        host = urlsplit(item.value).hostname or ""
        if host.casefold() not in _HUGGINGFACE_HOSTS:
            notes.append("unsupported_claim_host_ignored")
            continue
        candidates.append(
            UpstreamCandidate(
                repo_id=repo_id,
                file_name=file_name,
                source=PROPOSAL_SOURCE_GGUF_HEADER,
            )
        )
        repos.add(repo_id)

    deduped: list[UpstreamCandidate] = []
    seen: set[tuple[str, str | None]] = set()
    for candidate in candidates:
        key = (candidate.repo_id, candidate.file_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    if len(repos) > UPSTREAM_MAX_CANDIDATE_REPOS:
        notes.append("candidate_repositories_exceed_limit")
        return CandidateProposals(
            candidates=(),
            notes=tuple(dict.fromkeys(notes)),
        )

    return CandidateProposals(
        candidates=tuple(deduped),
        notes=tuple(dict.fromkeys(notes)),
    )


# ---------------------------------------------------------------------------
# Local digest groups (local byte-identity evidence only, never proof)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalLayerDigestGroup:
    """Registrations sharing one locally declared model-layer digest.

    This is LOCAL byte-identity evidence: the digest is declared by the
    local manifests, not recomputed from the blobs. It connects
    registrations but never proves upstream identity.
    """

    model_layer_digest: str
    registrations: tuple[str, ...]
    note: str = "local_byte_identity_claim_only_not_upstream_proof"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_layer_digest": self.model_layer_digest,
            "registrations": list(self.registrations),
            "note": self.note,
        }


def group_registrations_by_model_layer_digest(
    *,
    models_root: Path | None = None,
    records: Sequence[ManifestLayerRecord] | None = None,
) -> tuple[LocalLayerDigestGroup, ...]:
    """Group local registrations by their manifest-declared layer digest."""

    if records is None:
        if models_root is None:
            raise ValueError(
                "grouping requires a models root or explicit records"
            )
        records = collect_manifest_layer_records(models_root)

    grouped: dict[str, list[str]] = {}
    for record in records:
        if not isinstance(record, ManifestLayerRecord):
            continue
        if _DIGEST.fullmatch(record.model_layer_digest) is None:
            continue
        grouped.setdefault(record.model_layer_digest, [])
        if record.registry_identity not in grouped[record.model_layer_digest]:
            grouped[record.model_layer_digest].append(record.registry_identity)

    return tuple(
        LocalLayerDigestGroup(
            model_layer_digest=digest,
            registrations=tuple(sorted(set(registrations))),
        )
        for digest, registrations in sorted(grouped.items())
    )


# ---------------------------------------------------------------------------
# Phase 3a — Explicitly gated local full-blob hashing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalBlobHashPlan:
    """Disclosed plan for hashing one selected local blob.

    Contains no local path: the plan is what may be shown to the owner
    before any hashing happens.
    """

    size_bytes: int
    bytes_to_read: int
    chunk_count: int
    io_cost_note: str = "full-file-read-single-pass"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalBlobHashAuthorization:
    """Explicit owner authorization for one selected blob.

    ``acknowledged_size_bytes`` and ``acknowledged_bytes_to_read`` must
    match the disclosed plan exactly; any mismatch refuses to hash.
    """

    artifact_label: str
    acknowledged_size_bytes: int
    acknowledged_bytes_to_read: int


class LocalBlobHashNotAuthorized(RuntimeError):
    """Raised when full-blob hashing is attempted without explicit,
    size-consistent authorization. No file content is read in that case."""


@dataclass(frozen=True)
class LocalBlobHashResult:
    """Result of one authorized blob hash. Contains no local path."""

    artifact_label: str
    computed_sha256: str | None
    size_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_local_blob_hash(blob_path: Path) -> LocalBlobHashPlan:
    """Disclose size and estimated I/O cost before any hashing happens.

    Uses stat metadata only; the file is not read here.
    """

    size_bytes = Path(blob_path).stat().st_size
    if size_bytes < 0:
        raise OSError("negative blob size")
    chunk_count = max(1, -(-size_bytes // _LOCAL_BLOB_HASH_CHUNK_BYTES))
    return LocalBlobHashPlan(
        size_bytes=size_bytes,
        bytes_to_read=size_bytes,
        chunk_count=chunk_count,
    )


def compute_local_blob_sha256(
    blob_path: Path,
    *,
    plan: LocalBlobHashPlan,
    authorization: LocalBlobHashAuthorization | None,
) -> LocalBlobHashResult:
    """Hash one selected local blob, only under explicit authorization.

    Fails closed with ``LocalBlobHashNotAuthorized`` — without reading any
    file content — when authorization is missing, malformed, or does not
    exactly acknowledge the disclosed plan.
    """

    if not isinstance(plan, LocalBlobHashPlan):
        raise LocalBlobHashNotAuthorized("hashing requires a disclosed plan")

    if not isinstance(authorization, LocalBlobHashAuthorization):
        raise LocalBlobHashNotAuthorized(
            "no explicit authorization for this artifact"
        )

    label = authorization.artifact_label.strip()
    if (
        not label
        or _has_control_characters(label)
        or "\\" in label
        or ".." in label
        or label.startswith(("/", "."))
        or len(label) > 512
    ):
        raise LocalBlobHashNotAuthorized("malformed artifact authorization label")

    if authorization.acknowledged_size_bytes != plan.size_bytes:
        raise LocalBlobHashNotAuthorized(
            "authorization does not acknowledge the disclosed file size"
        )
    if authorization.acknowledged_bytes_to_read != plan.bytes_to_read:
        raise LocalBlobHashNotAuthorized(
            "authorization does not acknowledge the disclosed read cost"
        )

    blob_path = Path(blob_path)
    size_bytes = blob_path.stat().st_size
    if size_bytes != plan.size_bytes:
        raise LocalBlobHashNotAuthorized(
            "file size changed since the plan was disclosed"
        )

    digest = hashlib.sha256()
    with blob_path.open("rb") as handle:
        while True:
            chunk = handle.read(_LOCAL_BLOB_HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)

    return LocalBlobHashResult(
        artifact_label=label,
        computed_sha256=digest.hexdigest(),
        size_bytes=size_bytes,
    )


# ---------------------------------------------------------------------------
# Phase 3b — Bounded upstream evidence retrieval (explicit network gate)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpstreamNetworkGate:
    """Explicit authorization to fetch evidence from candidate repos only.

    Requests are bounded to the listed repos, one request per repo, under
    fixed module caps.
    """

    allow_network: bool
    repo_ids: tuple[str, ...]


class UpstreamNetworkNotAuthorized(RuntimeError):
    """Raised when upstream network access is attempted without an explicit
    gate. No request is made in that case."""


_UPSTREAM_FILE_RECORD_TYPE = "file"


@dataclass(frozen=True)
class UpstreamFileRecord:
    """One provider-published upstream file digest record (independent
    evidence of byte identity only)."""

    repo_id: str
    file_name: str
    sha256_hex: str | None
    size_bytes: int | None
    source: str = UPSTREAM_EVIDENCE_SOURCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "file_name": self.file_name,
            "sha256_hex": self.sha256_hex,
            "size_bytes": self.size_bytes,
            "source": self.source,
        }


@dataclass(frozen=True)
class UpstreamFetchFailure:
    """One bounded, deterministic, privacy-safe fetch failure."""

    repo_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UpstreamFetchResult:
    """Records and failures from one bounded upstream evidence fetch."""

    records: tuple[UpstreamFileRecord, ...] = ()
    failures: tuple[UpstreamFetchFailure, ...] = ()
    requests_made: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [record.to_dict() for record in self.records],
            "failures": [failure.to_dict() for failure in self.failures],
            "requests_made": self.requests_made,
        }


class _NoRedirects(HTTPRedirectHandler):
    """Refuse redirects: upstream fetches are bounded to exact URLs."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(newurl, code, "upstream redirect refused", headers, fp)


def _normalize_provider_digest(value: object) -> str | None:
    if isinstance(value, str):
        match = _DIGEST.fullmatch(value.strip())
        if match is not None:
            return match.group(1)
        if _BLOB_SHA256_RE.fullmatch(value.strip()) is not None:
            return value.strip()
    return None


def _parse_tree_entry(
    repo_id: str,
    entry: object,
) -> UpstreamFileRecord | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("type") != _UPSTREAM_FILE_RECORD_TYPE:
        return None

    path = entry.get("path")
    if not _file_name_is_well_formed(path):
        return None

    size = entry.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        size_bytes = None
    else:
        size_bytes = size

    lfs = entry.get("lfs")
    sha256_hex = None
    if isinstance(lfs, dict):
        sha256_hex = _normalize_provider_digest(lfs.get("oid"))

    return UpstreamFileRecord(
        repo_id=repo_id,
        file_name=path,
        sha256_hex=sha256_hex,
        size_bytes=size_bytes,
    )


def _huggingface_tree_fetcher(repo_id: str) -> bytes:
    """Fetch the bounded provider tree JSON for one explicitly supplied repo.

    One exact-URL request, no proxies, no redirects, hard response cap,
    fixed timeout. No search endpoints and no file content downloads.
    """

    request = Request(_UPSTREAM_TREE_URL.format(repo_id=repo_id))
    opener = build_opener(ProxyHandler({}), _NoRedirects())
    with opener.open(request, timeout=_UPSTREAM_TIMEOUT_SECONDS) as response:
        return response.read(_UPSTREAM_MAX_RESPONSE_BYTES + 1)


def fetch_upstream_file_records(
    repo_ids: Sequence[str],
    *,
    gate: UpstreamNetworkGate | None,
    fetcher: Callable[[str], bytes] | None = None,
) -> UpstreamFetchResult:
    """Retrieve provider-published file evidence, bounded to gate repos.

    Fails closed with ``UpstreamNetworkNotAuthorized`` — making no request
    — when the gate is missing, does not explicitly allow network access,
    does not authorize the requested repos, or exceeds the fixed repo cap.
    """

    if not isinstance(gate, UpstreamNetworkGate) or not gate.allow_network:
        raise UpstreamNetworkNotAuthorized(
            "upstream network access requires an explicit gate"
        )

    unique_repo_ids: list[str] = []
    for repo_id in repo_ids:
        if not _repo_id_is_well_formed(repo_id):
            raise ValueError("malformed candidate repository id")
        if repo_id not in unique_repo_ids:
            unique_repo_ids.append(repo_id)

    if not unique_repo_ids:
        raise ValueError("no candidate repositories to fetch")

    if len(unique_repo_ids) > UPSTREAM_MAX_CANDIDATE_REPOS:
        raise ValueError("candidate repositories exceed the fixed cap")

    for repo_id in unique_repo_ids:
        if repo_id not in gate.repo_ids:
            raise UpstreamNetworkNotAuthorized(
                "candidate repository not covered by the explicit gate"
            )

    resolved_fetcher = fetcher or _huggingface_tree_fetcher
    records: list[UpstreamFileRecord] = []
    failures: list[UpstreamFetchFailure] = []

    for repo_id in unique_repo_ids:
        try:
            payload = resolved_fetcher(repo_id)
        except (OSError, URLError, ValueError):
            failures.append(
                UpstreamFetchFailure(
                    repo_id=repo_id,
                    reason="upstream_network_failure",
                )
            )
            continue

        if len(payload) > _UPSTREAM_MAX_RESPONSE_BYTES:
            failures.append(
                UpstreamFetchFailure(
                    repo_id=repo_id,
                    reason="upstream_response_too_large",
                )
            )
            continue

        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeError, ValueError):
            failures.append(
                UpstreamFetchFailure(
                    repo_id=repo_id,
                    reason="upstream_response_malformed",
                )
            )
            continue

        if not isinstance(decoded, list):
            failures.append(
                UpstreamFetchFailure(
                    repo_id=repo_id,
                    reason="upstream_response_malformed",
                )
            )
            continue

        if len(decoded) > _UPSTREAM_MAX_RECORDS:
            failures.append(
                UpstreamFetchFailure(
                    repo_id=repo_id,
                    reason="upstream_records_limit_exceeded",
                )
            )
            continue

        for entry in decoded:
            record = _parse_tree_entry(repo_id, entry)
            if record is None:
                continue
            records.append(record)

    return UpstreamFetchResult(
        records=tuple(records),
        failures=tuple(failures),
        requests_made=len(unique_repo_ids),
    )


# ---------------------------------------------------------------------------
# Phase 2 — Upstream binding validator (pure, fail-closed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpstreamBindingResult:
    """Exact identity-evidence result for one selected local artifact.

    ``bound`` requires a unique byte-identity match against
    provider-published digests. ``upstream_authorship_verified``,
    ``lineage_verified``, and ``workload_suitability_assessed`` are always
    ``False`` in V1 — byte identity to a hosted file proves nothing about
    who authored it or whether it suits any workload.
    """

    status: UpstreamBindingStatus
    reasons: tuple[str, ...]
    computed_blob_sha256: str | None = None
    local_blob_size: int | None = None
    matched_repo_id: str | None = None
    matched_file_name: str | None = None
    matched_sha256: str | None = None
    trust_root: str | None = None
    upstream_authorship_verified: bool = False
    lineage_verified: bool = False
    workload_suitability_assessed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _verified_candidate(item: object) -> UpstreamCandidate | None:
    if not isinstance(item, UpstreamCandidate):
        return None
    if not _repo_id_is_well_formed(item.repo_id):
        return None
    if item.file_name is not None and not _file_name_is_well_formed(
        item.file_name
    ):
        return None
    return item


def verify_upstream_binding(
    *,
    computed_blob_sha256: str | None,
    local_blob_size: int | None,
    candidates: Sequence[UpstreamCandidate] = (),
    provider_records: Sequence[UpstreamFileRecord] = (),
    manifest_layer_digest_claim: str | None = None,
    manifest_layer_size_claim: int | None = None,
    quantized_by_claim: str | None = None,
) -> UpstreamBindingResult:
    """Bind one selected local artifact to an upstream file or report why not.

    Pure and deterministic: accepts the *computed* digest of the selected
    blob (produced only under the explicit local hashing gate) plus
    explicitly supplied candidates and provider-published records. Fails
    closed: missing, malformed, conflicting, or ambiguous evidence yields
    ``unknown``, definitive mismatches yield ``unbound``; only a unique,
    size-consistent provider-digest match yields ``bound``. Reasons
    contain no paths, no evidence values, and no credentials.
    """

    def _finish(status: UpstreamBindingStatus, specific: tuple[str, ...]) -> (
        UpstreamBindingResult
    ):
        if status == "bound":
            extra: tuple[str, ...] = ()
        elif quantized_by_claim:
            extra = ("quantized_derivative_not_excluded",)
        else:
            extra = ()
        return UpstreamBindingResult(
            status=status,
            reasons=specific + extra + _BASE_NONVERIFICATION_REASONS,
            computed_blob_sha256=(
                computed_blob_sha256
                if computed_blob_sha256 is not None
                and _BLOB_SHA256_RE.fullmatch(computed_blob_sha256) is not None
                else None
            ),
            local_blob_size=local_blob_size,
            trust_root=(
                UPSTREAM_FILE_DIGEST_TRUST_ROOT if status == "bound" else None
            ),
        )

    # The local blob hash must already exist, produced under the explicit
    # hashing gate. Hashing never happens implicitly here.
    if computed_blob_sha256 is None:
        return _finish("unknown", ("local_blob_hash_not_available",))
    computed_match = _BLOB_SHA256_RE.fullmatch(computed_blob_sha256)
    if computed_match is None:
        return _finish("unknown", ("malformed_blob_hash_input",))
    computed_hex = computed_match.group(0)

    if (
        isinstance(local_blob_size, bool)
        or not isinstance(local_blob_size, int)
        or local_blob_size < 0
    ):
        return _finish("unknown", ("local_blob_size_unavailable",))

    # Manifest-declared digests and sizes are claims, not evidence of the
    # blob bytes; a mismatch is itself decisive local-modification evidence.
    if manifest_layer_digest_claim is not None:
        claim_match = _DIGEST.fullmatch(manifest_layer_digest_claim)
        if claim_match is None:
            return _finish("unknown", ("malformed_manifest_digest_claim",))
        if claim_match.group(1) != computed_hex:
            return _finish("unbound", ("blob_manifest_digest_mismatch",))
    if manifest_layer_size_claim is not None:
        if (
            isinstance(manifest_layer_size_claim, bool)
            or not isinstance(manifest_layer_size_claim, int)
            or manifest_layer_size_claim < 0
        ):
            return _finish("unknown", ("malformed_manifest_size_claim",))
        if manifest_layer_size_claim != local_blob_size:
            return _finish("unbound", ("blob_manifest_size_mismatch",))
    manifest_digest_consistent = manifest_layer_digest_claim is not None

    usable_candidates: list[UpstreamCandidate] = []
    malformed_candidates = False
    for item in candidates:
        verified = _verified_candidate(item)
        if verified is not None:
            usable_candidates.append(verified)
        else:
            malformed_candidates = True

    if not candidates:
        return _finish("unknown", ("no_candidate_evidence",))
    if not usable_candidates:
        return _finish("unknown", ("no_usable_candidate_evidence",))

    canonical_records: dict[tuple[str, str], set[tuple[str | None, int | None]]] = {}
    malformed_records = False
    for record in provider_records:
        if (
            not isinstance(record, UpstreamFileRecord)
            or not _repo_id_is_well_formed(record.repo_id)
            or not _file_name_is_well_formed(record.file_name)
            or (
                record.sha256_hex is not None
                and _BLOB_SHA256_RE.fullmatch(record.sha256_hex) is None
            )
            or (
                record.size_bytes is not None
                and (
                    isinstance(record.size_bytes, bool)
                    or not isinstance(record.size_bytes, int)
                    or record.size_bytes < 0
                )
            )
        ):
            malformed_records = True
            continue
        canonical_records.setdefault(
            (record.repo_id, record.file_name), set()
        ).add((record.sha256_hex, record.size_bytes))

    # Conflicting provider records cannot identify one upstream file.
    conflicting = {
        key
        for key, values in canonical_records.items()
        if len({sha for sha, _size in values}) > 1
        or len({size for _sha, size in values}) > 1
    }
    if conflicting:
        return _finish("unknown", ("conflicting_provider_evidence",))

    # Records outside the explicitly proposed candidates are never used.
    considered: dict[tuple[str, str], tuple[str | None, int | None]] = {}
    outside_records = False
    for (repo_id, file_name), values in canonical_records.items():
        if not any(
            candidate.repo_id == repo_id
            and (candidate.file_name is None or candidate.file_name == file_name)
            for candidate in usable_candidates
        ):
            outside_records = True
            continue
        considered[(repo_id, file_name)] = next(iter(values))

    if not considered:
        return _finish(
            "unknown",
            ("no_provider_evidence_for_candidates",)
            + (("malformed_candidates_ignored",) if malformed_candidates else ())
            + (("malformed_provider_records_ignored",) if malformed_records else ()),
        )

    matches = {
        (repo_id, file_name): (sha, size)
        for (repo_id, file_name), (sha, size) in considered.items()
        if sha == computed_hex
    }

    if len(matches) > 1:
        return _finish("unknown", ("ambiguous_upstream_match",))

    if not matches:
        if all(sha is None for sha, _size in considered.values()):
            # Without a provider-published digest there is nothing to
            # compare against; this cannot be a definitive negative.
            specific: list[str] = ["missing_provider_digest"]
            status: UpstreamBindingStatus = "unknown"
        else:
            specific = ["no_provider_digest_match"]
            status = "unbound"
        if malformed_candidates:
            specific.append("malformed_candidates_ignored")
        if malformed_records:
            specific.append("malformed_provider_records_ignored")
        if outside_records:
            specific.append("provider_records_outside_candidates_ignored")
        return _finish(status, tuple(specific))

    (matched_repo_id, matched_file_name), (matched_sha, matched_size) = (
        next(iter(matches.items()))
    )

    if matched_size is None:
        size_reason = "provider_size_not_available"
    elif matched_size == local_blob_size:
        size_reason = "provider_size_match"
    else:
        # A digest match contradicted by a size record cannot be bound.
        return _finish("unknown", ("conflicting_size_evidence",))

    manifest_reason = (
        "manifest_layer_digest_consistent"
        if manifest_digest_consistent
        else "manifest_layer_digest_claim_absent"
    )

    specific = (
        "blob_sha256_match",
        size_reason,
        manifest_reason,
        "unique_upstream_match",
    )
    if malformed_candidates:
        specific += ("malformed_candidates_ignored",)
    if malformed_records:
        specific += ("malformed_provider_records_ignored",)
    if outside_records:
        specific += ("provider_records_outside_candidates_ignored",)

    result = _finish("bound", specific)
    assert result.status == "bound"
    return UpstreamBindingResult(
        status="bound",
        reasons=result.reasons,
        computed_blob_sha256=computed_hex,
        local_blob_size=local_blob_size,
        matched_repo_id=matched_repo_id,
        matched_file_name=matched_file_name,
        matched_sha256=matched_sha,
        trust_root=UPSTREAM_FILE_DIGEST_TRUST_ROOT,
        upstream_authorship_verified=False,
        lineage_verified=False,
        workload_suitability_assessed=False,
    )