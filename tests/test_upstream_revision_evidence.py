"""Synthetic-fixture tests for M10B Phase 2F upstream revision evidence producer.

All tests use injected fetchers. No live network calls are made.
No model files are read. No GPU is used.

Coverage:
- Validation helpers (_revision_is_immutable, _file_name_is_safe, etc.)
- Gate absent / allow_network=False / wrong repo -> RevisionNetworkNotAuthorized
- Valid gate with injected fetcher (proves no live network required)
- Immutable SHA extraction (valid, missing, floating, malformed)
- Pipeline tag extraction (valid, missing, malformed)
- Revision-pinned tree URL used (not floating main/master)
- File records: LFS digest/size, non-LFS file, zero-file, multi-file
- Network and parse failures: info call, tree call, oversized, bad JSON
- Task applicability always "repository", never "artifact_file"
- to_revision_bound_file_evidence conversion (valid, None sha, None size)
- to_provider_task_evidence conversion and applicability preserved
- Phase 2E integration regression: repository-only task -> "unknown", not "associated"
- No recommendation promotion
"""

import json
import unittest
from urllib.error import URLError

from liongateos_model_advisor.upstream_revision_evidence import (
    REVISION_EVIDENCE_SOURCE,
    REVISION_TASK_SOURCE,
    RevisionEvidenceFail,
    RevisionEvidenceResult,
    RevisionFileRecord,
    RevisionNetworkGate,
    RevisionNetworkNotAuthorized,
    RevisionTaskRecord,
    _file_name_is_safe,
    _normalize_pipeline_tag,
    _normalize_sha256,
    _revision_is_immutable,
    fetch_revision_evidence,
    to_provider_task_evidence,
    to_revision_bound_file_evidence,
)

# ---------------------------------------------------------------------------
# Shared fixture constants
# ---------------------------------------------------------------------------

_REPO_ID = "owner/mymodel"
_VALID_SHA = "a" * 40           # valid 40-char hex commit SHA
_VALID_SHA_64 = "a" * 64        # valid 64-char hex (longer SHA variant)
_FILE_SHA256 = "b" * 64         # valid 64-char hex LFS oid
_FILE_SIZE = 4096
_FILE_NAME = "mymodel.gguf"
_PIPELINE_TAG = "text-generation"
_GATE = RevisionNetworkGate(allow_network=True, repo_id=_REPO_ID)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _info_bytes(sha=_VALID_SHA, pipeline_tag=_PIPELINE_TAG,
                omit_sha=False, omit_tag=False) -> bytes:
    """Build a synthetic repo-info JSON payload."""
    data: dict = {}
    if not omit_sha:
        data["sha"] = sha
    if not omit_tag:
        data["pipeline_tag"] = pipeline_tag
    return json.dumps(data).encode()


def _tree_bytes(entries=()) -> bytes:
    """Build a synthetic file-tree JSON payload."""
    return json.dumps(list(entries)).encode()


def _lfs_entry(path=_FILE_NAME, oid=_FILE_SHA256, size=_FILE_SIZE) -> dict:
    """Build a synthetic LFS file entry."""
    return {
        "type": "file",
        "path": path,
        "size": size,
        "lfs": {"oid": oid, "size": size, "pointerSize": 134},
    }


def _plain_entry(path="README.md", size=512) -> dict:
    """Build a synthetic non-LFS file entry (no sha256 available)."""
    return {"type": "file", "path": path, "size": size}


def _dir_entry(path="subdir") -> dict:
    """Build a synthetic directory entry (should be ignored)."""
    return {"type": "directory", "path": path}


def _make_fetchers(info=None, tree=None):
    """Return (info_fetcher, tree_fetcher) pair from fixed response bytes."""
    def _info(repo_id):
        return info if info is not None else _info_bytes()

    def _tree(repo_id, revision):
        return tree if tree is not None else _tree_bytes()

    return _info, _tree


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class TestRevisionIsImmutable(unittest.TestCase):

    def test_valid_40_char_hex(self):
        self.assertTrue(_revision_is_immutable("a" * 40))

    def test_valid_64_char_hex(self):
        self.assertTrue(_revision_is_immutable("f" * 64))

    def test_valid_mixed_hex(self):
        self.assertTrue(_revision_is_immutable("0123456789abcdef" * 2 + "01234567"))

    def test_floating_main_rejected(self):
        self.assertFalse(_revision_is_immutable("main"))

    def test_floating_master_rejected(self):
        self.assertFalse(_revision_is_immutable("master"))

    def test_floating_head_rejected(self):
        self.assertFalse(_revision_is_immutable("HEAD"))

    def test_version_tag_rejected(self):
        self.assertFalse(_revision_is_immutable("v1.0"))

    def test_too_short_rejected(self):
        self.assertFalse(_revision_is_immutable("a" * 39))

    def test_uppercase_hex_rejected(self):
        # _REVISION_RE requires lowercase only
        self.assertFalse(_revision_is_immutable("A" * 40))

    def test_non_hex_chars_rejected(self):
        self.assertFalse(_revision_is_immutable("g" * 40))

    def test_empty_rejected(self):
        self.assertFalse(_revision_is_immutable(""))

    def test_none_rejected(self):
        self.assertFalse(_revision_is_immutable(None))


class TestFileNameIsSafe(unittest.TestCase):

    def test_simple_gguf(self):
        self.assertTrue(_file_name_is_safe("model.gguf"))

    def test_path_with_subdirectory(self):
        self.assertTrue(_file_name_is_safe("models/model.gguf"))

    def test_traversal_rejected(self):
        self.assertFalse(_file_name_is_safe("../etc/passwd"))

    def test_absolute_path_rejected(self):
        self.assertFalse(_file_name_is_safe("/etc/passwd"))

    def test_empty_rejected(self):
        self.assertFalse(_file_name_is_safe(""))

    def test_none_rejected(self):
        self.assertFalse(_file_name_is_safe(None))


class TestNormalizeSha256(unittest.TestCase):

    def test_valid_64_hex(self):
        self.assertEqual(_normalize_sha256("b" * 64), "b" * 64)

    def test_uppercase_rejected(self):
        self.assertIsNone(_normalize_sha256("B" * 64))

    def test_too_short_rejected(self):
        self.assertIsNone(_normalize_sha256("b" * 63))

    def test_none_rejected(self):
        self.assertIsNone(_normalize_sha256(None))


class TestNormalizePipelineTag(unittest.TestCase):

    def test_valid_tag(self):
        self.assertEqual(_normalize_pipeline_tag("text-generation"), "text-generation")

    def test_empty_returns_none(self):
        self.assertIsNone(_normalize_pipeline_tag(""))

    def test_whitespace_only_returns_none(self):
        self.assertIsNone(_normalize_pipeline_tag("   "))

    def test_none_returns_none(self):
        self.assertIsNone(_normalize_pipeline_tag(None))

    def test_control_char_rejected(self):
        self.assertIsNone(_normalize_pipeline_tag("text\x00gen"))


# ---------------------------------------------------------------------------
# Gate enforcement
# ---------------------------------------------------------------------------

class TestGateEnforcement(unittest.TestCase):

    def test_gate_none_raises(self):
        with self.assertRaises(RevisionNetworkNotAuthorized):
            fetch_revision_evidence(
                _REPO_ID,
                gate=None,
                info_fetcher=lambda r: _info_bytes(),
                tree_fetcher=lambda r, v: _tree_bytes(),
            )

    def test_gate_allow_network_false_raises(self):
        gate = RevisionNetworkGate(allow_network=False, repo_id=_REPO_ID)
        with self.assertRaises(RevisionNetworkNotAuthorized):
            fetch_revision_evidence(
                _REPO_ID,
                gate=gate,
                info_fetcher=lambda r: _info_bytes(),
                tree_fetcher=lambda r, v: _tree_bytes(),
            )

    def test_gate_wrong_repo_raises(self):
        gate = RevisionNetworkGate(allow_network=True, repo_id="other/repo")
        with self.assertRaises(RevisionNetworkNotAuthorized):
            fetch_revision_evidence(
                _REPO_ID,
                gate=gate,
                info_fetcher=lambda r: _info_bytes(),
                tree_fetcher=lambda r, v: _tree_bytes(),
            )

    def test_gate_absent_no_live_network(self):
        # Confirm the exception is raised before any fetcher could be called.
        called = []

        def info_fetcher(r):
            called.append("info")
            return _info_bytes()

        def tree_fetcher(r, v):
            called.append("tree")
            return _tree_bytes()

        with self.assertRaises(RevisionNetworkNotAuthorized):
            fetch_revision_evidence(
                _REPO_ID,
                gate=None,
                info_fetcher=info_fetcher,
                tree_fetcher=tree_fetcher,
            )
        self.assertEqual(called, [], "no fetcher should be called without a gate")

    def test_malformed_repo_id_returns_failure_not_raise(self):
        # A malformed repo_id returns a failure result, not a gate raise.
        result = fetch_revision_evidence(
            "not-valid",   # missing slash -> malformed
            gate=None,     # no gate: but malformed repo_id is caught first
            info_fetcher=lambda r: _info_bytes(),
            tree_fetcher=lambda r, v: _tree_bytes(),
        )
        self.assertIsInstance(result, RevisionEvidenceResult)
        self.assertIsNone(result.revision)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].reason, "malformed_repo_id")


# ---------------------------------------------------------------------------
# Info call parsing
# ---------------------------------------------------------------------------

class TestInfoParsing(unittest.TestCase):

    def _fetch(self, info_bytes, tree_bytes=None):
        return fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: info_bytes,
            tree_fetcher=lambda r, v: (tree_bytes or _tree_bytes()),
        )

    def test_valid_sha_extracted(self):
        result = self._fetch(_info_bytes(sha=_VALID_SHA))
        self.assertEqual(result.revision, _VALID_SHA)
        self.assertEqual(len(result.failures), 0)

    def test_valid_sha_64_char_accepted(self):
        result = self._fetch(_info_bytes(sha=_VALID_SHA_64))
        self.assertEqual(result.revision, _VALID_SHA_64)

    def test_missing_sha_returns_failure(self):
        result = self._fetch(_info_bytes(omit_sha=True))
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "revision_sha_missing")

    def test_floating_sha_returns_failure(self):
        result = self._fetch(_info_bytes(sha="main"))
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "revision_sha_not_immutable")

    def test_short_sha_returns_failure(self):
        result = self._fetch(_info_bytes(sha="a" * 39))
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "revision_sha_not_immutable")

    def test_uppercase_sha_returns_failure(self):
        result = self._fetch(_info_bytes(sha="A" * 40))
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "revision_sha_not_immutable")

    def test_pipeline_tag_extracted(self):
        result = self._fetch(_info_bytes(pipeline_tag=_PIPELINE_TAG))
        self.assertEqual(len(result.task_records), 1)
        self.assertEqual(result.task_records[0].task, _PIPELINE_TAG)

    def test_missing_pipeline_tag_no_task_records(self):
        result = self._fetch(_info_bytes(omit_tag=True))
        self.assertEqual(len(result.task_records), 0)

    def test_malformed_pipeline_tag_no_task_records(self):
        result = self._fetch(_info_bytes(pipeline_tag="bad\x00tag"))
        self.assertEqual(len(result.task_records), 0)

    def test_info_response_malformed_json(self):
        result = self._fetch(b"not json {{")
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "info_response_malformed")

    def test_info_response_not_object(self):
        result = self._fetch(json.dumps([1, 2, 3]).encode())
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "info_response_not_object")

    def test_info_response_too_large(self):
        big = b"x" * (2 * 1024 * 1024 + 1)
        result = self._fetch(big)
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "info_response_too_large")

    def test_info_network_failure(self):
        def bad_info(r):
            raise URLError("simulated failure")

        result = fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=bad_info,
            tree_fetcher=lambda r, v: _tree_bytes(),
        )
        self.assertIsNone(result.revision)
        self.assertEqual(result.failures[0].reason, "info_network_failure")


# ---------------------------------------------------------------------------
# Tree call and revision pinning
# ---------------------------------------------------------------------------

class TestTreeParsing(unittest.TestCase):

    def _fetch(self, tree_bytes, info_bytes=None):
        return fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: (info_bytes or _info_bytes()),
            tree_fetcher=lambda r, v: tree_bytes,
        )

    def test_revision_pinned_tree_not_floating_main(self):
        """Verify the tree fetcher receives the SHA, not 'main'."""
        captured = []

        def tree_fetcher(repo_id, revision):
            captured.append(revision)
            return _tree_bytes()

        fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: _info_bytes(sha=_VALID_SHA),
            tree_fetcher=tree_fetcher,
        )

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0], _VALID_SHA)
        self.assertNotEqual(captured[0], "main")
        self.assertNotEqual(captured[0], "master")

    def test_revision_tree_url_template_has_no_floating_ref(self):
        from liongateos_model_advisor.upstream_revision_evidence import (
            _REVISION_TREE_URL,
        )
        self.assertIn("{revision}", _REVISION_TREE_URL)
        self.assertNotIn("/main", _REVISION_TREE_URL)
        self.assertNotIn("/master", _REVISION_TREE_URL)

    def test_lfs_file_record_extracted(self):
        result = self._fetch(_tree_bytes([_lfs_entry()]))
        self.assertEqual(len(result.file_records), 1)
        rec = result.file_records[0]
        self.assertEqual(rec.file_name, _FILE_NAME)
        self.assertEqual(rec.sha256_hex, _FILE_SHA256)
        self.assertEqual(rec.size_bytes, _FILE_SIZE)
        self.assertEqual(rec.revision, _VALID_SHA)
        self.assertEqual(rec.repo_id, _REPO_ID)
        self.assertEqual(rec.source, REVISION_EVIDENCE_SOURCE)

    def test_non_lfs_file_has_no_sha256(self):
        result = self._fetch(_tree_bytes([_plain_entry()]))
        self.assertEqual(len(result.file_records), 1)
        self.assertIsNone(result.file_records[0].sha256_hex)

    def test_directory_entries_ignored(self):
        result = self._fetch(_tree_bytes([_dir_entry(), _lfs_entry()]))
        self.assertEqual(len(result.file_records), 1)
        self.assertEqual(result.file_records[0].file_name, _FILE_NAME)

    def test_zero_file_response(self):
        result = self._fetch(_tree_bytes([]))
        self.assertEqual(len(result.file_records), 0)
        self.assertEqual(len(result.failures), 0)

    def test_multi_file_response(self):
        entries = [
            _lfs_entry("model-q4.gguf", "1" * 64, 2048),
            _lfs_entry("model-q8.gguf", "2" * 64, 4096),
            _plain_entry("README.md"),
        ]
        result = self._fetch(_tree_bytes(entries))
        self.assertEqual(len(result.file_records), 3)

    def test_file_size_preserved(self):
        result = self._fetch(_tree_bytes([_lfs_entry(size=99999)]))
        self.assertEqual(result.file_records[0].size_bytes, 99999)

    def test_tree_response_malformed_json(self):
        result = self._fetch(b"not json {{")
        self.assertEqual(len(result.file_records), 0)
        self.assertEqual(result.failures[0].reason, "tree_response_malformed")
        # revision still set from info call
        self.assertEqual(result.revision, _VALID_SHA)

    def test_tree_response_not_array(self):
        result = self._fetch(json.dumps({"unexpected": "object"}).encode())
        self.assertEqual(result.failures[0].reason, "tree_response_not_array")
        self.assertEqual(result.revision, _VALID_SHA)

    def test_tree_response_too_large(self):
        big = b"x" * (2 * 1024 * 1024 + 1)
        result = self._fetch(big)
        self.assertEqual(result.failures[0].reason, "tree_response_too_large")
        self.assertEqual(result.revision, _VALID_SHA)

    def test_tree_records_limit_exceeded(self):
        # Build 513 entries (> 512 cap)
        entries = [_lfs_entry(f"model{i}.gguf", "a" * 64, 100) for i in range(513)]
        result = self._fetch(_tree_bytes(entries))
        self.assertEqual(result.failures[0].reason, "tree_records_limit_exceeded")
        self.assertEqual(result.revision, _VALID_SHA)

    def test_tree_network_failure(self):
        def bad_tree(r, v):
            raise URLError("simulated tree failure")

        result = fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: _info_bytes(),
            tree_fetcher=bad_tree,
        )
        self.assertEqual(result.failures[0].reason, "tree_network_failure")
        # revision is set even when tree call fails
        self.assertEqual(result.revision, _VALID_SHA)


# ---------------------------------------------------------------------------
# Task applicability
# ---------------------------------------------------------------------------

class TestTaskApplicability(unittest.TestCase):

    def _fetch_with_tag(self, tag=_PIPELINE_TAG):
        return fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: _info_bytes(pipeline_tag=tag),
            tree_fetcher=lambda r, v: _tree_bytes([_lfs_entry()]),
        )

    def test_task_applicability_always_repository(self):
        result = self._fetch_with_tag()
        self.assertEqual(len(result.task_records), 1)
        self.assertEqual(result.task_records[0].applicability, "repository")

    def test_task_applicability_never_artifact_file(self):
        result = self._fetch_with_tag()
        for rec in result.task_records:
            self.assertNotEqual(rec.applicability, "artifact_file")

    def test_multi_file_still_repository_applicability(self):
        # Even a repo with many GGUF files stays at "repository" applicability.
        result = fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: _info_bytes(pipeline_tag="text-generation"),
            tree_fetcher=lambda r, v: _tree_bytes([
                _lfs_entry("model-q4.gguf", "1" * 64, 1000),
                _lfs_entry("model-q8.gguf", "2" * 64, 2000),
            ]),
        )
        self.assertEqual(len(result.task_records), 1)
        self.assertEqual(result.task_records[0].applicability, "repository")

    def test_task_revision_matches_file_revision(self):
        result = self._fetch_with_tag()
        self.assertEqual(result.task_records[0].revision, _VALID_SHA)
        if result.file_records:
            self.assertEqual(
                result.task_records[0].revision,
                result.file_records[0].revision,
            )

    def test_task_source_is_revision_task_source(self):
        result = self._fetch_with_tag()
        self.assertEqual(result.task_records[0].source, REVISION_TASK_SOURCE)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

class TestToRevisionBoundFileEvidence(unittest.TestCase):

    def test_valid_lfs_record_converts(self):
        record = RevisionFileRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            file_name=_FILE_NAME,
            sha256_hex=_FILE_SHA256,
            size_bytes=_FILE_SIZE,
        )
        result = to_revision_bound_file_evidence(record)
        self.assertIsNotNone(result)
        self.assertEqual(result.repo_id, _REPO_ID)
        self.assertEqual(result.revision, _VALID_SHA)
        self.assertEqual(result.file_name, _FILE_NAME)
        self.assertEqual(result.sha256_hex, _FILE_SHA256)
        self.assertEqual(result.size_bytes, _FILE_SIZE)
        self.assertEqual(result.source, REVISION_EVIDENCE_SOURCE)

    def test_missing_sha256_returns_none(self):
        record = RevisionFileRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            file_name=_FILE_NAME,
            sha256_hex=None,
            size_bytes=_FILE_SIZE,
        )
        self.assertIsNone(to_revision_bound_file_evidence(record))

    def test_missing_size_returns_none(self):
        record = RevisionFileRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            file_name=_FILE_NAME,
            sha256_hex=_FILE_SHA256,
            size_bytes=None,
        )
        self.assertIsNone(to_revision_bound_file_evidence(record))


class TestToProviderTaskEvidence(unittest.TestCase):

    def test_converts_correctly(self):
        record = RevisionTaskRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            task=_PIPELINE_TAG,
        )
        result = to_provider_task_evidence(record)
        self.assertEqual(result.repo_id, _REPO_ID)
        self.assertEqual(result.revision, _VALID_SHA)
        self.assertEqual(result.task, _PIPELINE_TAG)
        self.assertEqual(result.source, REVISION_TASK_SOURCE)
        self.assertIsNone(result.file_name)

    def test_applicability_is_repository(self):
        record = RevisionTaskRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            task=_PIPELINE_TAG,
        )
        result = to_provider_task_evidence(record)
        self.assertEqual(result.applicability, "repository")

    def test_applicability_never_artifact_file(self):
        record = RevisionTaskRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            task=_PIPELINE_TAG,
        )
        result = to_provider_task_evidence(record)
        self.assertNotEqual(result.applicability, "artifact_file")


# ---------------------------------------------------------------------------
# Phase 2E integration regression
# ---------------------------------------------------------------------------

class TestPhase2EIntegration(unittest.TestCase):
    """Verify that repository-level task evidence produces "unknown" in Phase
    2E, not "associated". This regression confirms the fail-closed boundary."""

    def _build_fixtures(self):
        """Build a complete, internally consistent set of Phase 2E fixtures."""
        from liongateos_model_advisor.artifact_task_evidence import (
            LocalArtifactTaskContext,
            RevisionBoundFileEvidence,
            associate_artifact_task_evidence,
        )
        from liongateos_model_advisor.model_origin_evidence import (
            LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
            OriginEvidenceResult,
        )
        from liongateos_model_advisor.upstream_identity_binding import (
            UPSTREAM_FILE_DIGEST_TRUST_ROOT,
            UpstreamBindingResult,
        )

        # Shared digest values
        manifest_hex = "c" * 64
        manifest_digest = "sha256:" + manifest_hex
        blob_sha256 = _FILE_SHA256          # "b" * 64
        layer_digest = "sha256:" + blob_sha256
        blob_size = _FILE_SIZE              # 4096

        # Phase 2E LocalArtifactTaskContext
        context = LocalArtifactTaskContext(
            model_id="ollama:owner/mymodel",
            artifact_id="ollama:owner/mymodel:artifact",
            registry_identity="library/owner/mymodel",
            manifest_digest=manifest_digest,
        )

        # M09A anchored OriginEvidenceResult
        origin = OriginEvidenceResult(
            model_name="owner/mymodel",
            registry_identity="library/owner/mymodel",
            status="anchored",
            reasons=("local_manifest_digest_match",),
            verified_manifest_digest=manifest_digest,
            model_layer_digest=layer_digest,
            upstream_origin_verified=False,
            trust_root=LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
        )

        # M09B bound UpstreamBindingResult
        binding = UpstreamBindingResult(
            status="bound",
            reasons=("blob_sha256_match",),
            computed_blob_sha256=blob_sha256,
            local_blob_size=blob_size,
            matched_repo_id=_REPO_ID,
            matched_file_name=_FILE_NAME,
            matched_sha256=blob_sha256,
            trust_root=UPSTREAM_FILE_DIGEST_TRUST_ROOT,
        )

        # Phase 2F RevisionBoundFileEvidence (via conversion helper)
        file_record = RevisionFileRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            file_name=_FILE_NAME,
            sha256_hex=blob_sha256,
            size_bytes=blob_size,
        )
        revision_file_ev = to_revision_bound_file_evidence(file_record)
        self.assertIsNotNone(revision_file_ev)

        # Phase 2F ProviderTaskEvidence with applicability="repository" (via helper)
        task_record = RevisionTaskRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            task=_PIPELINE_TAG,
        )
        provider_task_ev = to_provider_task_evidence(task_record)

        return (
            context,
            origin,
            binding,
            revision_file_ev,
            provider_task_ev,
            associate_artifact_task_evidence,
        )

    def test_repository_task_produces_unknown_not_associated(self):
        """Core regression: HF pipeline_tag (repository-level) must not
        yield 'associated' from Phase 2E validator."""
        (
            context,
            origin,
            binding,
            revision_file_ev,
            provider_task_ev,
            associate,
        ) = self._build_fixtures()

        result = associate(
            context=context,
            origin=origin,
            binding=binding,
            task=_PIPELINE_TAG,
            revision_files=(revision_file_ev,),
            task_records=(provider_task_ev,),
        )

        self.assertEqual(
            result.status,
            "unknown",
            "Repository-level task evidence must yield 'unknown', not 'associated'",
        )
        self.assertIn("task_applicability_not_artifact_scoped", result.reasons)
        self.assertNotEqual(result.status, "associated")

    def test_no_recommendation_promotion(self):
        """An 'unknown' result must never promote recommendations."""
        (
            context,
            origin,
            binding,
            revision_file_ev,
            provider_task_ev,
            associate,
        ) = self._build_fixtures()

        result = associate(
            context=context,
            origin=origin,
            binding=binding,
            task=_PIPELINE_TAG,
            revision_files=(revision_file_ev,),
            task_records=(provider_task_ev,),
        )

        self.assertFalse(
            result.recommendation_promoted,
            "recommendation_promoted must always be False",
        )
        self.assertFalse(
            result.task_performance_verified,
            "task_performance_verified must always be False",
        )

    def test_result_contains_nonverification_reasons(self):
        """Result reasons must explicitly state what was not verified."""
        (
            context,
            origin,
            binding,
            revision_file_ev,
            provider_task_ev,
            associate,
        ) = self._build_fixtures()

        result = associate(
            context=context,
            origin=origin,
            binding=binding,
            task=_PIPELINE_TAG,
            revision_files=(revision_file_ev,),
            task_records=(provider_task_ev,),
        )

        self.assertIn("task_performance_not_verified", result.reasons)
        self.assertIn("recommendation_not_promoted", result.reasons)


# ---------------------------------------------------------------------------
# to_dict round-trip
# ---------------------------------------------------------------------------

class TestToDictRoundTrip(unittest.TestCase):

    def test_revision_evidence_result_to_dict(self):
        result = fetch_revision_evidence(
            _REPO_ID,
            gate=_GATE,
            info_fetcher=lambda r: _info_bytes(),
            tree_fetcher=lambda r, v: _tree_bytes([_lfs_entry()]),
        )
        d = result.to_dict()
        self.assertEqual(d["repo_id"], _REPO_ID)
        self.assertEqual(d["revision"], _VALID_SHA)
        self.assertEqual(len(d["file_records"]), 1)
        self.assertEqual(len(d["task_records"]), 1)
        self.assertEqual(d["task_records"][0]["applicability"], "repository")

    def test_revision_file_record_to_dict(self):
        record = RevisionFileRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            file_name=_FILE_NAME,
            sha256_hex=_FILE_SHA256,
            size_bytes=_FILE_SIZE,
        )
        d = record.to_dict()
        self.assertEqual(d["sha256_hex"], _FILE_SHA256)
        self.assertEqual(d["size_bytes"], _FILE_SIZE)
        self.assertEqual(d["source"], REVISION_EVIDENCE_SOURCE)

    def test_revision_task_record_to_dict(self):
        record = RevisionTaskRecord(
            repo_id=_REPO_ID,
            revision=_VALID_SHA,
            task=_PIPELINE_TAG,
        )
        d = record.to_dict()
        self.assertEqual(d["applicability"], "repository")
        self.assertEqual(d["source"], REVISION_TASK_SOURCE)


if __name__ == "__main__":
    unittest.main()
