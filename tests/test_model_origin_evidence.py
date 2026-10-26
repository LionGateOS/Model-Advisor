"""M09A model-origin evidence validator tests (simulated fixtures only).

Every fixture in this file is SIMULATED: synthetic manifest bytes written
into a temporary directory and synthetic digest records created by the test
itself. NOTHING here represents verified real-world provenance, and none of
these tests fetch, download, hash, or execute any real model artifact.

The only cryptographic assertion exercised is over the synthetic small
manifest file created by each test, digested locally, under the documented
local-record trust root constant.
"""

import json
import tempfile
import unittest
from pathlib import Path

from liongateos_model_advisor.model_origin_evidence import (
    ArtifactOriginRecord,
    LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
    OriginEvidenceRecord,
    validate_local_origin_evidence,
)
from liongateos_model_advisor.model_profile import ModelArtifact, ModelIdentity
from liongateos_model_advisor.qualification import ModelQualification
from liongateos_model_advisor.recommendation import recommend_local_model


MODEL_LAYER_MEDIA_TYPE = "application/vnd.ollama.image.model"

NOW = 1_000_000_000.0


class ModelOriginEvidenceTests(unittest.TestCase):
    """Validation behaviour under the documented test trust root."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.model_layer_hex = "b" * 64

        self.manifest_payload = {
            "schemaVersion": 2,
            "layers": [
                {
                    "mediaType": MODEL_LAYER_MEDIA_TYPE,
                    "digest": "sha256:" + self.model_layer_hex,
                    "size": 10,
                },
            ],
        }
        self.manifest_path = self.root / "manifest.json"
        self.write_manifest_payload(self.manifest_payload)

        manifest_hex = self.digest_of(self.manifest_path)
        self.registry_identity = "registry.ollama.ai/library/example/latest"
        self.manifest_digest = "sha256:" + manifest_hex
        self.model_layer_digest = "sha256:" + self.model_layer_hex

        self.artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        self.evidence = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            upstream_origin=None,
            captured_at=NOW - 60.0,
        )

    def tearDown(self):
        self.temp.cleanup()

    # -- fixture helpers ---------------------------------------------------

    def write_manifest_payload(self, payload):
        text = json.dumps(payload)
        self.manifest_path.write_text(text, encoding="utf-8")

    def digest_of(self, path):
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()

    def validate(self, **overrides):
        kwargs = {
            "artifact": self.artifact,
            "evidence_records": (self.evidence,),
            "trust_root": LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
            "now": NOW,
            "manifest_path": self.manifest_path,
        }
        kwargs.update(overrides)
        return validate_local_origin_evidence(**kwargs)

    # -- acceptance --------------------------------------------------------

    def test_valid_evidence_under_documented_trust_root_is_anchored(self):
        result = self.validate()
        self.assertEqual(result.status, "anchored")
        self.assertEqual(result.reasons[0], "local_manifest_digest_match")
        self.assertEqual(result.reasons[1], "model_layer_digest_chain_match")
        self.assertEqual(result.registry_identity, self.registry_identity)
        self.assertEqual(
            result.verified_manifest_digest,
            self.manifest_digest,
        )
        self.assertEqual(result.model_layer_digest, self.model_layer_digest)
        self.assertEqual(result.trust_root, LOCAL_MANIFEST_DIGEST_TRUST_ROOT)

    def test_result_dict_is_json_serializable(self):
        result = self.validate()
        decoded = json.loads(json.dumps(result.to_dict()))
        self.assertEqual(decoded["status"], "anchored")

    # -- upstream claims are never proof -----------------------------------

    def test_upstream_claim_is_recorded_but_never_verified(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            upstream_origin="hf.co/example/model-repo",
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "anchored")
        self.assertFalse(result.upstream_origin_verified)
        self.assertIn("upstream_origin_not_verified", result.reasons)
        self.assertEqual(result.upstream_origin_claim, "hf.co/example/model-repo")

    def test_incorrect_upstream_identity_claim_still_not_proof(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            upstream_origin="hf.co/someone/someother-repo",
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertFalse(result.upstream_origin_verified)
        self.assertIn("upstream_origin_not_verified", result.reasons)

    # -- trust root and identity claims ------------------------------------

    def test_unsupported_trust_root_rejected(self):
        result = self.validate(trust_root="example-test-trust-root")
        self.assertEqual(result.status, "rejected")
        self.assertIn("unsupported_trust_root", result.reasons)

    def test_remote_artifact_out_of_scope_rejected(self):
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="remote",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("remote_artifact_out_of_scope", result.reasons)

    def test_malformed_artifact_identity_rejected(self):
        artifact = ArtifactOriginRecord(
            model_name="bad name:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_traversal_artifact_name_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="../evil:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_traversal_artifact_name_in_middle_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="team/../evil:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_dot_component_artifact_name_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="./evil:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_dot_component_in_middle_artifact_name_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="team/./evil:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_traversal_registry_identity_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity="registry.ollama.ai/../library/example/latest",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn(
            "malformed_artifact_registry_identity",
            result.reasons,
        )

    def test_dot_component_registry_identity_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity="registry.ollama.ai/./library/example/latest",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn(
            "malformed_artifact_registry_identity",
            result.reasons,
        )

    def test_traversal_evidence_registry_identity_fails_closed(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity="registry.ollama.ai/../library/example/latest",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn(
            "malformed_evidence_registry_identity",
            result.reasons,
        )

    def test_dotted_artifact_and_registry_identity_still_anchored(self):
        artifact = ArtifactOriginRecord(
            model_name="model.v2:latest",
            location="local",
            registry_identity="registry.ollama.ai/library/model.v2/latest",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        evidence = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity="registry.ollama.ai/library/model.v2/latest",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(artifact=artifact, evidence_records=(evidence,))
        self.assertEqual(result.status, "anchored")

    def test_non_string_artifact_name_fails_closed(self):
        artifact = ArtifactOriginRecord(
            model_name=12345,
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_identity", result.reasons)

    def test_artifact_name_and_registry_identity_mismatch_rejected(self):
        artifact = ArtifactOriginRecord(
            model_name="other-model:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("artifact_name_registry_mismatch", result.reasons)

    def test_missing_artifact_manifest_digest_record_rejected(self):
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=None,
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn(
            "missing_artifact_manifest_digest_record",
            result.reasons,
        )

    def test_malformed_artifact_manifest_digest_rejected(self):
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest="sha256:not-a-real-digest",
            model_layer_digest=self.model_layer_digest,
        )
        result = self.validate(artifact=artifact)
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_artifact_manifest_digest", result.reasons)

    # -- evidence records: names and URLs are never proof ------------------

    def test_name_as_evidence_source_rejected(self):
        record = OriginEvidenceRecord(
            source="example-model:latest",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("unsupported_evidence_source", result.reasons)

    def test_url_as_evidence_source_rejected(self):
        record = OriginEvidenceRecord(
            source="https://huggingface.co/user/example-repo",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("unsupported_evidence_source", result.reasons)

    def test_architecture_match_not_accepted_as_proof(self):
        record = OriginEvidenceRecord(
            source="architecture-match:example-llama",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("unsupported_evidence_source", result.reasons)

    def test_evidence_record_with_unknown_fields_fails_closed(self):
        with self.assertRaises(TypeError):
            OriginEvidenceRecord(
                source="local-registry-manifest-record",
                registry_identity=self.registry_identity,
                manifest_digest=self.manifest_digest,
                model_layer_digest=self.model_layer_digest,
                captured_at=NOW - 60.0,
                architecture="llama",
            )

    def test_non_record_evidence_object_rejected(self):
        result = self.validate(evidence_records=({"digest": "junk"},))
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_evidence_record", result.reasons)

    def test_malformed_evidence_digest_rejected(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest="sha256:zz",
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_evidence_manifest_digest", result.reasons)

    def test_missing_evidence_rejected(self):
        result = self.validate(evidence_records=())
        self.assertEqual(result.status, "rejected")
        self.assertIn("missing_evidence", result.reasons)

    # -- ambiguity, conflict, staleness ------------------------------------

    def test_conflicting_evidence_rejected(self):
        other_layer = "sha256:" + "c" * 64
        conflicting = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=other_layer,
            captured_at=NOW - 60.0,
        )
        result = self.validate(
            evidence_records=(self.evidence, conflicting),
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("conflicting_evidence", result.reasons)

    def test_artifact_evidence_identity_mismatch_rejected(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity="registry.ollama.ai/library/example/v9",
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("artifact_registry_identity_mismatch", result.reasons)

    def test_artifact_evidence_digest_mismatch_rejected(self):
        record = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest="sha256:" + "d" * 64,
            model_layer_digest=self.model_layer_digest,
            captured_at=NOW - 60.0,
        )
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("artifact_manifest_digest_mismatch", result.reasons)

    def test_ambiguous_upstream_origin_claim_rejected(self):
        other = OriginEvidenceRecord(
            source="local-registry-manifest-record",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
            upstream_origin="mirror.example/some/repo",
            captured_at=NOW - 60.0,
        )
        record = self.replace(self.evidence, upstream_origin="example/repo")
        result = self.validate(evidence_records=(record, other))
        self.assertEqual(result.status, "rejected")
        self.assertIn("ambiguous_upstream_origin_claim", result.reasons)

    def test_stale_evidence_rejected(self):
        record = self.replace(self.evidence, captured_at=NOW - 30 * 86400 - 1)
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("stale_evidence", result.reasons)

    def test_explicit_max_age_makes_recent_evidence_stale(self):
        record = self.replace(self.evidence, captured_at=NOW - 3600.0)
        result = self.validate(
            evidence_records=(record,),
            max_age_seconds=60,
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("stale_evidence", result.reasons)

    def test_future_evidence_timestamp_rejected(self):
        record = self.replace(self.evidence, captured_at=NOW + 10.0)
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("future_evidence_timestamp", result.reasons)

    def test_missing_evidence_timestamp_rejected(self):
        record = self.replace(self.evidence, captured_at=None)
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("no_evidence_timestamp", result.reasons)

    def test_malformed_evidence_timestamp_rejected(self):
        record = self.replace(self.evidence, captured_at="yesterday")
        result = self.validate(evidence_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_evidence_timestamp", result.reasons)

    # -- manifest binding (the only real cryptographic check) --------------

    def test_modified_artifact_manifest_rejected(self):
        modified = dict(self.manifest_payload)
        modified["schemaVersion"] = 3
        self.write_manifest_payload(modified)
        result = self.validate()
        self.assertEqual(result.status, "rejected")
        self.assertIn("manifest_content_mismatch", result.reasons)

    def test_manifest_file_unavailable_rejected(self):
        result = self.validate(manifest_path=None)
        self.assertEqual(result.status, "rejected")
        self.assertIn("manifest_file_unavailable", result.reasons)

    def test_manifest_file_unreadable_rejected(self):
        result = self.validate(manifest_path=self.root / "missing.json")
        self.assertEqual(result.status, "rejected")
        self.assertIn("manifest_file_unreadable", result.reasons)

    def test_injected_reader_returning_non_bytes_fails_closed(self):
        result = self.validate(manifest_reader=lambda _path: "text")
        self.assertEqual(result.status, "rejected")
        self.assertIn("manifest_file_unreadable", result.reasons)

    def test_layer_digest_chain_mismatch_rejected(self):
        payload = {
            "schemaVersion": 2,
            "layers": [
                {
                    "mediaType": MODEL_LAYER_MEDIA_TYPE,
                    "digest": "sha256:" + "f" * 64,
                    "size": 10,
                },
            ],
        }
        self.write_manifest_payload(payload)
        self.manifest_digest = "sha256:" + self.digest_of(self.manifest_path)
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        record = self.replace(self.evidence, manifest_digest=self.manifest_digest)
        result = self.validate(
            artifact=artifact,
            evidence_records=(record,),
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("layer_digest_chain_mismatch", result.reasons)

    def test_malformed_manifest_content_rejected(self):
        self.manifest_path.write_text("{broken-json", encoding="utf-8")
        self.manifest_digest = "sha256:" + self.digest_of(self.manifest_path)
        artifact = ArtifactOriginRecord(
            model_name="example:latest",
            location="local",
            registry_identity=self.registry_identity,
            manifest_digest=self.manifest_digest,
            model_layer_digest=self.model_layer_digest,
        )
        record = self.replace(self.evidence, manifest_digest=self.manifest_digest)
        result = self.validate(
            artifact=artifact,
            evidence_records=(record,),
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_manifest_content", result.reasons)

    # -- no automatic promotion into recommendations ------------------------

    def test_anchored_evidence_does_not_promote_workload_unknown(self):
        anchored = self.validate()
        self.assertEqual(anchored.status, "anchored")

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
        recommendation = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )
        self.assertEqual(recommendation.status, "workload_unknown")
        self.assertNotIn(
            LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
            recommendation.evidence_sources,
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def replace(record, **changes):
        base = {
            "source": record.source,
            "registry_identity": record.registry_identity,
            "manifest_digest": record.manifest_digest,
            "model_layer_digest": record.model_layer_digest,
            "upstream_origin": record.upstream_origin,
            "captured_at": record.captured_at,
        }
        base.update(changes)
        return OriginEvidenceRecord(**base)


if __name__ == "__main__":
    unittest.main()