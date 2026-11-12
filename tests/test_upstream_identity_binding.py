"""M09B upstream identity binding tests (synthetic fixtures only).

Everything here is SIMULATED: tiny synthetic files, synthetic digests, and
injected fake fetchers. No live model blob, no GPU, no external network.

The only cryptographic assertion exercised is over a few-byte synthetic
file created by the test itself, hashed locally under explicit
authorization, to prove gating and binding mechanics.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from liongateos_model_advisor.model_origin_evidence import (
    LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
)
from liongateos_model_advisor.model_profile import ModelArtifact, ModelIdentity
from liongateos_model_advisor.qualification import ModelQualification
from liongateos_model_advisor.recommendation import recommend_local_model
from liongateos_model_advisor.upstream_identity_binding import (
    GGUFIdentityClaims,
    LocalBlobHashAuthorization,
    LocalBlobHashNotAuthorized,
    LocalBlobHashPlan,
    LocalLayerDigestGroup,
    OwnerUpstreamMapping,
    PROPOSAL_SOURCE_GGUF_HEADER,
    PROPOSAL_SOURCE_OWNER_MAPPING,
    UPSTREAM_FILE_DIGEST_TRUST_ROOT,
    UpstreamCandidate,
    UpstreamFileRecord,
    UpstreamFetchFailure,
    UpstreamFetchResult,
    UpstreamNetworkGate,
    UpstreamNetworkNotAuthorized,
    compute_local_blob_sha256,
    extract_gguf_identity_claims,
    fetch_upstream_file_records,
    group_registrations_by_model_layer_digest,
    plan_local_blob_hash,
    propose_upstream_candidates,
    verify_upstream_binding,
)
from liongateos_model_advisor.model_profile import MODEL_SCHEMA_VERSION


BLOB_CONTENT = b"synthetic-local-blob"
BLOB_HEX = hashlib.sha256(BLOB_CONTENT).hexdigest()
UPSTREAM_HEX = hashlib.sha256(BLOB_CONTENT).hexdigest()
OTHER_HEX = hashlib.sha256(b"a-different-blob").hexdigest()

REPO = "owner/example-model-gguf"
FILE = "example-model-q4.gguf"

NOW = 1_000_000_000.0


class UpstreamBindingValidatorTests(unittest.TestCase):
    """Core binding validator rules (pure, no file or network I/O)."""

    def record(self, repo_id=REPO, file_name=FILE, sha=UPSTREAM_HEX, size=None):
        return UpstreamFileRecord(
            repo_id=repo_id,
            file_name=file_name,
            sha256_hex=sha,
            size_bytes=size,
        )

    def binding(self, **overrides):
        kwargs = {
            "computed_blob_sha256": BLOB_HEX,
            "local_blob_size": 10,
            "candidates": (
                UpstreamCandidate(
                    repo_id=REPO,
                    file_name=FILE,
                    source=PROPOSAL_SOURCE_OWNER_MAPPING,
                ),
            ),
            "provider_records": (self.record(size=10),),
        }
        kwargs.update(overrides)
        return verify_upstream_binding(**kwargs)

    # -- bound: correct local SHA-256 and upstream digest -------------------

    def test_matching_local_sha256_and_provider_digest_bind(self):
        result = self.binding(
            manifest_layer_digest_claim="sha256:" + BLOB_HEX,
        )
        self.assertEqual(result.status, "bound")
        self.assertIn("blob_sha256_match", result.reasons)
        self.assertIn("provider_size_match", result.reasons)
        self.assertIn("manifest_layer_digest_consistent", result.reasons)
        self.assertIn("unique_upstream_match", result.reasons)
        self.assertEqual(result.matched_repo_id, REPO)
        self.assertEqual(result.matched_file_name, FILE)
        self.assertEqual(result.matched_sha256, UPSTREAM_HEX)
        self.assertEqual(result.trust_root, UPSTREAM_FILE_DIGEST_TRUST_ROOT)
        # Byte identity never proves authorship, lineage, or suitability.
        self.assertFalse(result.upstream_authorship_verified)
        self.assertFalse(result.lineage_verified)
        self.assertFalse(result.workload_suitability_assessed)
        self.assertIn("workload_suitability_not_assessed", result.reasons)

    def test_binding_without_manifest_claim_absent_reason(self):
        result = self.binding()
        self.assertEqual(result.status, "bound")
        self.assertIn("manifest_layer_digest_claim_absent", result.reasons)

    def test_binding_still_requires_no_filename_discovery(self):
        result = self.binding(
            candidates=(
                UpstreamCandidate(
                    repo_id=REPO,
                    file_name=None,
                    source=PROPOSAL_SOURCE_GGUF_HEADER,
                ),
            ),
            provider_records=(
                self.record(file_name="toplevel.gguf", size=10),
                self.record(file_name="nested/other.gguf", sha=OTHER_HEX, size=11),
            ),
        )
        self.assertEqual(result.status, "bound")
        self.assertEqual(result.matched_file_name, "toplevel.gguf")

    # -- definitive negatives (unbound) -------------------------------------

    def test_wrong_sha256_is_unbound(self):
        result = self.binding(
            computed_blob_sha256=OTHER_HEX,
            provider_records=(self.record(sha=BLOB_HEX, size=10),),
        )
        self.assertEqual(result.status, "unbound")
        self.assertIn("no_provider_digest_match", result.reasons)
        self.assertIsNone(result.matched_repo_id)

    def test_wrong_upstream_file_size_rejected(self):
        result = self.binding(
            local_blob_size=10,
            provider_records=(self.record(size=999),),
        )
        self.assertNotEqual(result.status, "bound")
        self.assertIn("conflicting_size_evidence", result.reasons)

    def test_manifest_size_mismatch_is_unbound(self):
        result = self.binding(manifest_layer_size_claim=999)
        self.assertEqual(result.status, "unbound")
        self.assertIn("blob_manifest_size_mismatch", result.reasons)

    def test_local_manifest_digest_vs_actual_blob_mismatch_is_unbound(self):
        result = self.binding(manifest_layer_digest_claim="sha256:" + OTHER_HEX)
        self.assertEqual(result.status, "unbound")
        self.assertIn("blob_manifest_digest_mismatch", result.reasons)

    def test_forged_gguf_header_claim_is_not_proof(self):
        forged_repo = "fraudster/fake-repo"
        metadata = {
            "general.repo_url": f"https://huggingface.co/{forged_repo}",
        }
        claims = extract_gguf_identity_claims(metadata)
        proposals = propose_upstream_candidates(claims)
        self.assertEqual(
            proposals.candidates[0].source,
            PROPOSAL_SOURCE_GGUF_HEADER,
        )
        result = self.binding(
            candidates=proposals.candidates,
            provider_records=(self.record(repo_id=forged_repo, sha=OTHER_HEX),),
        )
        self.assertEqual(result.status, "unbound")
        self.assertIn("no_provider_digest_match", result.reasons)
        self.assertIsNone(result.trust_root)

    def test_incorrect_owner_mapping_is_not_proof(self):
        wrong_mapping = OwnerUpstreamMapping(
            registry_identity="library/example/latest",
            repo_id="someone/wrong-repo",
            file_name=FILE,
        )
        proposals = propose_upstream_candidates(claims=GGUFIdentityClaims(), owner_mappings=(wrong_mapping,))
        result = self.binding(
            candidates=proposals.candidates,
            provider_records=(self.record(repo_id="someone/wrong-repo", sha=OTHER_HEX, size=10),),
        )
        self.assertEqual(result.status, "unbound")
        self.assertIn("no_provider_digest_match", result.reasons)

    def test_quantized_derivative_mismatch_is_unbound_and_recorded(self):
        result = self.binding(
            quantized_by_claim="someone-else",
            provider_records=(self.record(sha=OTHER_HEX, size=10),),
        )
        self.assertEqual(result.status, "unbound")
        self.assertIn("quantized_derivative_not_excluded", result.reasons)

    # -- fail-closed unknowns ------------------------------------------------

    def test_missing_provider_digest_is_unknown(self):
        result = self.binding(provider_records=(self.record(sha=None, size=10),))
        self.assertEqual(result.status, "unknown")
        self.assertIn("missing_provider_digest", result.reasons)

    def test_missing_blob_hash_refuses_without_hashing(self):
        result = self.binding(computed_blob_sha256=None)
        self.assertEqual(result.status, "unknown")
        self.assertIn("local_blob_hash_not_available", result.reasons)

    def test_malformed_blob_hash_is_unknown(self):
        result = self.binding(computed_blob_sha256="not-a-digest")
        self.assertEqual(result.status, "unknown")
        self.assertIn("malformed_blob_hash_input", result.reasons)

    def test_missing_local_size_is_unknown(self):
        result = self.binding(local_blob_size=None)
        self.assertEqual(result.status, "unknown")
        self.assertIn("local_blob_size_unavailable", result.reasons)

    def test_no_candidates_is_unknown(self):
        result = self.binding(candidates=())
        self.assertEqual(result.status, "unknown")
        self.assertIn("no_candidate_evidence", result.reasons)

    def test_malformed_only_candidates_is_unknown(self):
        result = self.binding(
            candidates=(
                UpstreamCandidate(
                    repo_id="../traversal",
                    file_name=FILE,
                    source=PROPOSAL_SOURCE_OWNER_MAPPING,
                ),
            ),
        )
        self.assertEqual(result.status, "unknown")
        self.assertIn("no_usable_candidate_evidence", result.reasons)

    def test_conflicting_provider_records_are_unknown(self):
        result = self.binding(
            provider_records=(
                self.record(sha=BLOB_HEX, size=10),
                self.record(sha=OTHER_HEX, size=10),
            ),
        )
        self.assertEqual(result.status, "unknown")
        self.assertIn("conflicting_provider_evidence", result.reasons)

    def test_ambiguous_upstream_match_is_unknown(self):
        result = self.binding(
            candidates=(
                UpstreamCandidate(
                    repo_id=REPO,
                    file_name=None,
                    source=PROPOSAL_SOURCE_OWNER_MAPPING,
                ),
                UpstreamCandidate(
                    repo_id="owner/repo-b",
                    file_name=None,
                    source=PROPOSAL_SOURCE_OWNER_MAPPING,
                ),
            ),
            provider_records=(
                self.record(),
                self.record(repo_id="owner/repo-b"),
            ),
        )
        self.assertEqual(result.status, "unknown")
        self.assertIn("ambiguous_upstream_match", result.reasons)

    def test_malformed_manifest_digest_claim_is_unknown(self):
        result = self.binding(manifest_layer_digest_claim="sha256:zz")
        self.assertEqual(result.status, "unknown")
        self.assertIn("malformed_manifest_digest_claim", result.reasons)

    def test_records_outside_candidates_are_ignored(self):
        result = self.binding(
            provider_records=(
                self.record(repo_id="unrelated/other", size=10),
                self.record(size=10),
            ),
        )
        self.assertEqual(result.status, "bound")
        self.assertIn("provider_records_outside_candidates_ignored", result.reasons)

    def test_reasons_are_private_safe(self):
        bound = self.binding(manifest_layer_digest_claim=f"sha256:{BLOB_HEX}")
        unbound = self.binding(
            computed_blob_sha256=OTHER_HEX,
            provider_records=(self.record(sha=BLOB_HEX),),
        )
        unknown = self.binding(candidates=())
        for result in (bound, unbound, unknown):
            encoded = json.dumps(result.to_dict())
            self.assertNotIn("/home", encoded)
            self.assertNotIn("\\\\", encoded)
            for reason in result.reasons:
                self.assertTrue(reason == reason.strip())
                self.assertFalse(any(character.isspace() for character in reason))

    # -- helpers -------------------------------------------------------------


class ClaimExtractionTests(unittest.TestCase):
    """Phase 1: GGUF metadata claims are preserved but never verified."""

    def test_all_four_documented_claim_fields_extracted(self):
        metadata = {
            "general.architecture": "llama",
            "general.basename": "ExampleBase",
            "general.repo_url": f"https://huggingface.co/{REPO}",
            "general.quantized_by": "someone-trusted",
            "general.base_model.0.repo_url": (
                "https://huggingface.co/owner/base-model"
            ),
        }
        claims = extract_gguf_identity_claims(metadata)
        self.assertEqual(claims.basename.value, "ExampleBase")
        self.assertEqual(claims.repo_url.value, f"https://huggingface.co/{REPO}")
        self.assertEqual(claims.quantized_by.value, "someone-trusted")
        self.assertEqual(len(claims.base_model_repo_urls), 1)
        self.assertEqual(
            claims.base_model_repo_urls[0].field,
            "general.base_model.0.repo_url",
        )
        self.assertTrue(all(item.well_formed for item in claims.claims))
        self.assertTrue(claims.to_dict()["all_unverified"])

    def test_malformed_and_private_path_lineage_is_withheld(self):
        metadata = {
            "general.repo_url": "file:///home/owner/secret",
            "general.base_model.1.repo_url": "/home/owner/local/blob.gguf",
            "general.base_model.2.repo_url": "https://user:pass@huggingface.co/owner/repo",
            "general.base_model.3.repo_url": "https://127.0.0.1:8080/owner/repo",
            "general.basename": "../escape",
            "general.quantized_by": "C:\\Users\\me\\tool",
        }
        claims = extract_gguf_identity_claims(metadata)
        encoded = json.dumps(claims.to_dict())
        self.assertNotIn("/home", encoded)
        self.assertNotIn("user:pass", encoded)
        self.assertNotIn("127.0.0.1", encoded)
        self.assertFalse(all(item.well_formed for item in claims.claims))
        self.assertIsNone(claims.repo_url.value)
        self.assertIsNone(claims.basename.value)

    def test_missing_metadata_yields_no_claims(self):
        claims = extract_gguf_identity_claims({})
        self.assertIsNone(claims.basename)
        self.assertIsNone(claims.repo_url)
        self.assertIsNone(claims.quantized_by)
        self.assertEqual(claims.base_model_repo_urls, ())
        self.assertEqual(claims.claims, ())

    def test_non_mapping_metadata_rejected(self):
        with self.assertRaises(ValueError):
            extract_gguf_identity_claims("not-a-mapping")  # type: ignore[arg-type]

    def test_non_huggingface_host_claim_stored_but_not_proposed(self):
        claims = extract_gguf_identity_claims(
            {"general.repo_url": "https://mirror.example/owner/repo"}
        )
        proposals = propose_upstream_candidates(claims)
        self.assertEqual(proposals.candidates, ())
        self.assertIn("unsupported_claim_host_ignored", proposals.notes)

    def test_proposals_decline_candidate_cap(self):
        metadata = {
            key: f"https://huggingface.co/owner/repo{index}"
            for index, key in enumerate(
                [f"general.base_model.{index}.repo_url" for index in range(5)]
            )
        }
        claims = extract_gguf_identity_claims(metadata)
        proposals = propose_upstream_candidates(claims)
        self.assertEqual(proposals.candidates, ())
        self.assertIn("candidate_repositories_exceed_limit", proposals.notes)

    def test_owner_mapping_proposals_carry_owner_source(self):
        mapping = OwnerUpstreamMapping(
            registry_identity="registry.ollama.ai/library/example/latest",
            repo_id=REPO,
            file_name=FILE,
        )
        proposals = propose_upstream_candidates(
            GGUFIdentityClaims(),
            owner_mappings=(mapping,),
        )
        self.assertEqual(len(proposals.candidates), 1)
        self.assertEqual(
            proposals.candidates[0].source,
            PROPOSAL_SOURCE_OWNER_MAPPING,
        )

    def test_malformed_owner_mapping_declined(self):
        mapping = OwnerUpstreamMapping(
            registry_identity="../evil",
            repo_id=REPO,
        )
        proposals = propose_upstream_candidates(
            GGUFIdentityClaims(),
            owner_mappings=(mapping,),
        )
        self.assertEqual(proposals.candidates, ())
        self.assertIn("malformed_owner_mapping_ignored", proposals.notes)


class LocalDigestGroupTests(unittest.TestCase):
    """Shared model-layer digest connects registrations, never as proof."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        blob_hex = hashlib.sha256(BLOB_CONTENT).hexdigest()
        (self.root / "blobs").mkdir(parents=True)
        (self.root / "blobs" / ("sha256-" + blob_hex)).write_bytes(BLOB_CONTENT)

        self.manifest_payload = {
            "schemaVersion": 2,
            "from": f"huggingface.co/{REPO}",
            "layers": [
                {
                    "mediaType": "application/vnd.ollama.image.model",
                    "digest": "sha256:" + blob_hex,
                    "size": len(BLOB_CONTENT),
                },
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, relative):
        path = self.root / "manifests" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.manifest_payload), encoding="utf-8")
        return path

    def test_shared_model_layer_digest_groups_registrations(self):
        self.write_manifest("library/example/latest")
        self.write_manifest("library/example2/latest")
        groups = group_registrations_by_model_layer_digest(models_root=self.root)
        shared = [group for group in groups if len(group.registrations) >= 2]
        self.assertEqual(len(shared), 1)
        self.assertEqual(
            set(shared[0].registrations),
            {"library/example/latest", "library/example2/latest"},
        )
        self.assertEqual(
            shared[0].note,
            "local_byte_identity_claim_only_not_upstream_proof",
        )

    def test_from_label_preserved_as_claim(self):
        self.write_manifest("library/example/latest")
        from liongateos_model_advisor.ollama_manifest_identity import (
            collect_manifest_layer_records,
        )

        records = collect_manifest_layer_records(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0].from_label,
            f"huggingface.co/{REPO}",
        )
        self.assertTrue(records[0].from_label_well_formed)

    def test_private_path_from_label_withheld(self):
        self.manifest_payload = {
            "schemaVersion": 2,
            "from": "/home/owner/secret/model",
            "layers": self.manifest_payload["layers"],
        }
        self.write_manifest("library/example/latest")
        from liongateos_model_advisor.ollama_manifest_identity import (
            collect_manifest_layer_records,
        )

        records = collect_manifest_layer_records(self.root)
        self.assertIsNone(records[0].from_label)
        self.assertFalse(records[0].from_label_well_formed)

    def test_group_result_is_private_safe(self):
        self.write_manifest("library/example/latest")
        groups = group_registrations_by_model_layer_digest(models_root=self.root)
        encoded = json.dumps([group.to_dict() for group in groups])
        self.assertNotIn(str(self.root), encoded)
        self.assertNotIn("home", encoded)


class LocalBlobHashGateTests(unittest.TestCase):
    """Full-blob hashing requires explicit, size-consistent authorization."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.blob = self.root / "blob"
        self.blob.write_bytes(BLOB_CONTENT)
        self.plan = plan_local_blob_hash(self.blob)

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_discloses_size_and_cost_without_reading(self):
        self.assertEqual(self.plan.size_bytes, len(BLOB_CONTENT))
        self.assertEqual(self.plan.bytes_to_read, len(BLOB_CONTENT))
        self.assertEqual(self.plan.io_cost_note, "full-file-read-single-pass")
        encoded = json.dumps(self.plan.to_dict())
        self.assertNotIn(str(self.blob), encoded)

    def test_hashing_denied_without_explicit_authorization(self):
        with self.assertRaises(LocalBlobHashNotAuthorized):
            compute_local_blob_sha256(self.blob, plan=self.plan, authorization=None)

    def test_hashing_denied_with_mismatched_acknowledgement(self):
        bad = LocalBlobHashAuthorization(
            artifact_label="library/example/latest",
            acknowledged_size_bytes=self.plan.size_bytes + 1,
            acknowledged_bytes_to_read=self.plan.bytes_to_read,
        )
        with self.assertRaises(LocalBlobHashNotAuthorized):
            compute_local_blob_sha256(self.blob, plan=self.plan, authorization=bad)

        bad_cost = LocalBlobHashAuthorization(
            artifact_label="library/example/latest",
            acknowledged_size_bytes=self.plan.size_bytes,
            acknowledged_bytes_to_read=self.plan.bytes_to_read + 1,
        )
        with self.assertRaises(LocalBlobHashNotAuthorized):
            compute_local_blob_sha256(self.blob, plan=self.plan, authorization=bad_cost)

    def test_authorized_hash_computes_correct_sha256(self):
        authorization = LocalBlobHashAuthorization(
            artifact_label="library/example/latest",
            acknowledged_size_bytes=self.plan.size_bytes,
            acknowledged_bytes_to_read=self.plan.bytes_to_read,
        )
        result = compute_local_blob_sha256(
            self.blob, plan=self.plan, authorization=authorization
        )
        self.assertEqual(result.computed_sha256, BLOB_HEX)
        self.assertEqual(result.size_bytes, len(BLOB_CONTENT))
        encoding = json.dumps(result.to_dict())
        self.assertNotIn(str(self.blob), encoding)

    def test_changed_size_after_plan_refused(self):
        authorization = LocalBlobHashAuthorization(
            artifact_label="library/example/latest",
            acknowledged_size_bytes=self.plan.size_bytes,
            acknowledged_bytes_to_read=self.plan.bytes_to_read,
        )
        self.blob.write_bytes(BLOB_CONTENT + b"-extra")
        with self.assertRaises(LocalBlobHashNotAuthorized):
            compute_local_blob_sha256(self.blob, plan=self.plan, authorization=authorization)

    def test_malformed_authorization_label_refused(self):
        authorization = LocalBlobHashAuthorization(
            artifact_label="/home/owner/secret",
            acknowledged_size_bytes=self.plan.size_bytes,
            acknowledged_bytes_to_read=self.plan.bytes_to_read,
        )
        with self.assertRaises(LocalBlobHashNotAuthorized):
            compute_local_blob_sha256(self.blob, plan=self.plan, authorization=authorization)


class UpstreamNetworkGateTests(unittest.TestCase):
    """Upstream network access is bounded and requires an explicit gate."""

    def fake_fetcher(self, payload=b'[]', state=None):
        def fetch(repo_id):
            if state is not None:
                state.append(repo_id)
            if isinstance(payload, Exception):
                raise payload
            if callable(payload):
                return payload(repo_id)
            return payload

        return fetch

    def gate(self):
        return UpstreamNetworkGate(
            allow_network=True,
            repo_ids=(REPO, "owner/repo-a", "owner/repo-b", "owner/repo-c", "owner/repo-d"),
        )

    def test_network_denied_without_explicit_gate(self):
        with self.assertRaises(UpstreamNetworkNotAuthorized):
            fetch_upstream_file_records(
                (REPO,), gate=None, fetcher=self.fake_fetcher()
            )

    def test_network_denied_when_gate_not_explicit(self):
        gate = UpstreamNetworkGate(allow_network=False, repo_ids=(REPO,))
        with self.assertRaises(UpstreamNetworkNotAuthorized):
            fetch_upstream_file_records(
                (REPO,), gate=gate, fetcher=self.fake_fetcher()
            )

    def test_malformed_repo_id_refused_before_any_request(self):
        state: list[str] = []
        with self.assertRaises(ValueError):
            fetch_upstream_file_records(
                ("../traversal",),
                gate=self.gate(),
                fetcher=self.fake_fetcher(state=state),
            )
        self.assertEqual(state, [])

    def test_requests_bounded_to_gate_repos(self):
        gate = UpstreamNetworkGate(allow_network=True, repo_ids=(REPO,))
        state: list[str] = []
        with self.assertRaises(UpstreamNetworkNotAuthorized):
            fetch_upstream_file_records(
                ("owner/other-repo",),
                gate=gate,
                fetcher=self.fake_fetcher(state=state),
            )
        self.assertEqual(state, [])

    def test_candidate_count_cap_enforced_without_requests(self):
        state: list[str] = []
        requested = ("a/b", "c/d", "e/f", "g/h", "i/j")
        with self.assertRaises(ValueError):
            fetch_upstream_file_records(
                requested,
                gate=UpstreamNetworkGate(allow_network=True, repo_ids=requested),
                fetcher=self.fake_fetcher(state=state),
            )
        self.assertEqual(state, [])

    def test_network_failure_recorded_privately_safe(self):
        result = fetch_upstream_file_records(
            (REPO,),
            gate=self.gate(),
            fetcher=self.fake_fetcher(payload=OSError("connection refused")),
        )
        self.assertEqual(result.records, ())
        self.assertEqual(
            result.failures,
            (UpstreamFetchFailure(repo_id=REPO, reason="upstream_network_failure"),),
        )

    def test_oversized_response_rejected(self):
        result = fetch_upstream_file_records(
            (REPO,),
            gate=self.gate(),
            fetcher=self.fake_fetcher(payload=b"x" * (2 * 1024 * 1024 + 1)),
        )
        self.assertEqual(
            result.failures[0].reason, "upstream_response_too_large"
        )
        self.assertEqual(result.records, ())

    def test_malformed_response_rejected(self):
        result = fetch_upstream_file_records(
            (REPO,),
            gate=self.gate(),
            fetcher=self.fake_fetcher(payload=b"{broken"),
        )
        self.assertEqual(
            result.failures[0].reason, "upstream_response_malformed"
        )

    def test_record_limit_enforced(self):
        entries = [
            {"type": "file", "path": f"f{i}.gguf", "size": 1}
            for i in range(513)
        ]
        result = fetch_upstream_file_records(
            (REPO,),
            gate=self.gate(),
            fetcher=self.fake_fetcher(payload=json.dumps(entries).encode()),
        )
        self.assertEqual(
            result.failures[0].reason, "upstream_records_limit_exceeded"
        )
        self.assertEqual(result.records, ())

    def test_valid_tree_payload_parsed_with_digest_normalization(self):
        payload = json.dumps(
            [
                {
                    "type": "file",
                    "path": FILE,
                    "size": len(BLOB_CONTENT),
                    "lfs": {"oid": "sha256:" + UPSTREAM_HEX, "size": len(BLOB_CONTENT)},
                },
                {
                    "type": "file",
                    "path": "plain.bin",
                    "size": 5,
                },
                {"type": "blob", "path": "ignored.gguf"},
            ]
        ).encode()
        result = fetch_upstream_file_records(
            (REPO,), gate=self.gate(), fetcher=self.fake_fetcher(payload=payload)
        )
        self.assertEqual(result.failures, ())
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(len(result.records), 2)
        first = result.records[0]
        self.assertEqual(first.sha256_hex, UPSTREAM_HEX)
        self.assertEqual(first.size_bytes, len(BLOB_CONTENT))
        second = result.records[1]
        self.assertIsNone(second.sha256_hex)
        self.assertEqual(
            second.source, "huggingface-provider-published-digest"
        )

    def test_fetch_result_roundtrip_is_private_safe(self):
        payload = json.dumps(
            [
                {"type": "file", "path": "f/../../escape.gguf", "size": 1},
                {"type": "file", "path": "ok.gguf", "size": 2,
                 "lfs": {"oid": UPSTREAM_HEX}},
            ]
        ).encode()
        result = fetch_upstream_file_records(
            (REPO,), gate=self.gate(), fetcher=self.fake_fetcher(payload=payload)
        )
        encoded = json.dumps(result.to_dict())
        self.assertIn("ok.gguf", encoded)
        self.assertNotIn("escape", encoded)


class BoundaryTests(unittest.TestCase):
    """No recommendation promotion; no public contract changes."""

    def test_bound_evidence_does_not_promote_workload_unknown(self):
        model = ModelIdentity(model_id="ollama:example", tasks=())
        artifact = ModelArtifact(
            artifact_id="artifact-1",
            model_id="ollama:example",
            location="local",
        )
        qualification = ModelQualification(
            model_id="ollama:example",
            artifact_id="artifact-1",
            runtime_name="ollama",
            status="qualified",
            execution_path="single_gpu",
        )
        result = verify_upstream_binding(
            computed_blob_sha256=BLOB_HEX,
            local_blob_size=10,
            candidates=(
                UpstreamCandidate(
                    repo_id=REPO,
                    file_name=FILE,
                    source=PROPOSAL_SOURCE_OWNER_MAPPING,
                ),
            ),
            provider_records=(
                UpstreamFileRecord(
                    repo_id=REPO,
                    file_name=FILE,
                    sha256_hex=UPSTREAM_HEX,
                    size_bytes=10,
                ),
            ),
        )
        self.assertEqual(result.status, "bound")
        recommendation = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )
        self.assertEqual(recommendation.status, "workload_unknown")
        evidence = recommendation.evidence_sources
        self.assertNotIn(
            UPSTREAM_FILE_DIGEST_TRUST_ROOT,
            evidence,
        )
        self.assertNotIn(LOCAL_MANIFEST_DIGEST_TRUST_ROOT, evidence)

    def test_public_model_profile_contract_keys_unchanged(self):
        artifact = ModelArtifact(
            artifact_id="artifact-1",
            model_id="ollama:example",
        )
        model = ModelIdentity(model_id="ollama:example")
        from dataclasses import asdict

        decoded = {
            "artifact": asdict(artifact),
            "model": asdict(model),
        }
        self.assertEqual(
            sorted(decoded["artifact"].keys()),
            [
                "artifact_id",
                "digest",
                "evidence",
                "format",
                "location",
                "model_id",
                "quantization",
                "registry_identity",
                "size_bytes",
            ],
        )
        self.assertEqual(
            sorted(decoded["model"].keys()),
            [
                "active_parameter_count",
                "architecture",
                "attention_head_count",
                "attention_head_count_kv",
                "attention_key_length",
                "attention_recurrent_layers",
                "attention_sliding_window",
                "attention_value_length",
                "block_count",
                "capabilities",
                "context_length",
                "display_name",
                "embedding_length",
                "evidence",
                "family",
                "full_attention_interval",
                "license",
                "model_id",
                "nextn_predict_layers",
                "parameter_count",
                "parameter_size_label",
                "ssm_conv_kernel",
                "ssm_group_count",
                "ssm_inner_size",
                "ssm_state_size",
                "ssm_time_step_rank",
                "tasks",
            ],
        )
        self.assertEqual(MODEL_SCHEMA_VERSION, "1")


if __name__ == "__main__":
    unittest.main()