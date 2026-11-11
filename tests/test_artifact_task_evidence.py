from __future__ import annotations

import json
import unittest
from dataclasses import asdict

from liongateos_model_advisor.artifact_task_evidence import (
    ArtifactTaskAssociationResult,
    LocalArtifactTaskContext,
    ProviderTaskEvidence,
    RevisionBoundFileEvidence,
    associate_artifact_task_evidence,
)
from liongateos_model_advisor.model_origin_evidence import (
    LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
    OriginEvidenceResult,
)
from liongateos_model_advisor.model_profile import ModelArtifact, ModelIdentity
from liongateos_model_advisor.qualification import ModelQualification
from liongateos_model_advisor.recommendation import recommend_local_model
from liongateos_model_advisor.upstream_identity_binding import (
    UPSTREAM_FILE_DIGEST_TRUST_ROOT,
    UpstreamBindingResult,
)


SHA = "a" * 64
OTHER_SHA = "b" * 64
REV = "1" * 40
OTHER_REV = "2" * 40
REPO = "owner/example"
FILE = "example-Q4_K_M.gguf"


class ArtifactTaskEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = LocalArtifactTaskContext(
            model_id="ollama:example",
            artifact_id="ollama:example:artifact",
            registry_identity="registry.ollama.ai/library/example/latest",
            manifest_digest="sha256:" + ("c" * 64),
        )
        self.origin = OriginEvidenceResult(
            model_name="example",
            registry_identity=self.context.registry_identity,
            status="anchored",
            reasons=("local_manifest_digest_match",),
            verified_manifest_digest=self.context.manifest_digest,
            model_layer_digest="sha256:" + SHA,
            upstream_origin_verified=False,
            trust_root=LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
        )
        self.binding = UpstreamBindingResult(
            status="bound",
            reasons=("blob_sha256_match",),
            computed_blob_sha256=SHA,
            local_blob_size=10,
            matched_repo_id=REPO,
            matched_file_name=FILE,
            matched_sha256=SHA,
            trust_root=UPSTREAM_FILE_DIGEST_TRUST_ROOT,
        )
        self.file_evidence = RevisionBoundFileEvidence(
            repo_id=REPO,
            revision=REV,
            file_name=FILE,
            sha256_hex=SHA,
            size_bytes=10,
            source="huggingface:revision-file",
        )
        self.task_evidence = ProviderTaskEvidence(
            repo_id=REPO,
            revision=REV,
            task="summarization",
            source="huggingface:revision-model-info",
            applicability="artifact_file",
            file_name=FILE,
        )

    def associate(self, **overrides):
        kwargs = {
            "context": self.context,
            "origin": self.origin,
            "binding": self.binding,
            "task": "summarization",
            "revision_files": (self.file_evidence,),
            "task_records": (self.task_evidence,),
        }
        kwargs.update(overrides)
        return associate_artifact_task_evidence(**kwargs)


    def test_wrong_local_artifact_id_is_rejected(self):
        context = LocalArtifactTaskContext(
            model_id=self.context.model_id,
            artifact_id="ollama:wrong:artifact",
            registry_identity=self.context.registry_identity,
            manifest_digest=self.context.manifest_digest,
        )
        result = self.associate(context=context)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_artifact_id_mismatch", result.reasons)

    def test_wrong_local_registry_identity_is_rejected(self):
        context = LocalArtifactTaskContext(
            model_id=self.context.model_id,
            artifact_id=self.context.artifact_id,
            registry_identity="registry.ollama.ai/library/other/latest",
            manifest_digest=self.context.manifest_digest,
        )
        result = self.associate(context=context)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_origin_context_mismatch", result.reasons)

    def test_wrong_local_model_identity_is_rejected(self):
        context = LocalArtifactTaskContext(
            model_id="ollama:other",
            artifact_id="ollama:other:artifact",
            registry_identity=self.context.registry_identity,
            manifest_digest=self.context.manifest_digest,
        )
        result = self.associate(context=context)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_origin_context_mismatch", result.reasons)

    def test_wrong_manifest_digest_is_rejected(self):
        context = LocalArtifactTaskContext(
            model_id=self.context.model_id,
            artifact_id=self.context.artifact_id,
            registry_identity=self.context.registry_identity,
            manifest_digest="sha256:" + OTHER_SHA,
        )
        result = self.associate(context=context)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_origin_context_mismatch", result.reasons)

    def test_unanchored_local_origin_is_rejected(self):
        origin = OriginEvidenceResult(
            model_name="example",
            registry_identity=self.context.registry_identity,
            status="rejected",
            reasons=("missing_evidence",),
        )
        result = self.associate(origin=origin)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_origin_not_anchored", result.reasons)

    def test_local_origin_blob_digest_must_match_bound_blob(self):
        origin = OriginEvidenceResult(
            model_name="example",
            registry_identity=self.context.registry_identity,
            status="anchored",
            reasons=("local_manifest_digest_match",),
            verified_manifest_digest=self.context.manifest_digest,
            model_layer_digest="sha256:" + OTHER_SHA,
            upstream_origin_verified=False,
            trust_root=LOCAL_MANIFEST_DIGEST_TRUST_ROOT,
        )
        result = self.associate(origin=origin)
        self.assertEqual(result.status, "rejected")
        self.assertIn("local_origin_blob_digest_mismatch", result.reasons)

    def test_exact_revision_bound_artifact_task_is_associated(self):
        result = self.associate()
        self.assertEqual(result.status, "associated")
        self.assertEqual(result.revision, REV)
        self.assertEqual(result.file_name, FILE)
        self.assertIn("artifact_scoped_task_metadata", result.reasons)
        self.assertFalse(result.task_performance_verified)
        self.assertFalse(result.recommendation_promoted)

    def test_result_is_json_serializable_and_contains_no_performance_claim(self):
        encoded = json.dumps(self.associate().to_dict())
        self.assertIn('"status": "associated"', encoded)
        self.assertIn('"task_performance_verified": false', encoded)
        self.assertIn('"recommendation_promoted": false', encoded)

    def test_missing_revision_file_evidence_is_unknown(self):
        result = self.associate(revision_files=())
        self.assertEqual(result.status, "unknown")
        self.assertIn("revision_bound_file_evidence_missing", result.reasons)

    def test_floating_revision_is_rejected_as_malformed(self):
        record = RevisionBoundFileEvidence(
            repo_id=REPO,
            revision="main",
            file_name=FILE,
            sha256_hex=SHA,
            size_bytes=10,
            source="huggingface:revision-file",
        )
        result = self.associate(revision_files=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("malformed_revision_bound_file_evidence", result.reasons)

    def test_revision_file_digest_mismatch_is_rejected(self):
        record = RevisionBoundFileEvidence(
            repo_id=REPO,
            revision=REV,
            file_name=FILE,
            sha256_hex=OTHER_SHA,
            size_bytes=10,
            source="huggingface:revision-file",
        )
        result = self.associate(revision_files=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("revision_file_digest_mismatch", result.reasons)

    def test_revision_file_size_mismatch_is_rejected(self):
        record = RevisionBoundFileEvidence(
            repo_id=REPO,
            revision=REV,
            file_name=FILE,
            sha256_hex=SHA,
            size_bytes=11,
            source="huggingface:revision-file",
        )
        result = self.associate(revision_files=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("revision_file_size_mismatch", result.reasons)

    def test_conflicting_revision_file_records_are_rejected(self):
        other = RevisionBoundFileEvidence(
            repo_id=REPO,
            revision=OTHER_REV,
            file_name=FILE,
            sha256_hex=SHA,
            size_bytes=10,
            source="huggingface:revision-file",
        )
        result = self.associate(revision_files=(self.file_evidence, other))
        self.assertEqual(result.status, "rejected")
        self.assertIn("conflicting_revision_bound_file_evidence", result.reasons)

    def test_missing_task_evidence_is_unknown(self):
        result = self.associate(task_records=())
        self.assertEqual(result.status, "unknown")
        self.assertIn("provider_task_evidence_missing", result.reasons)

    def test_repository_scoped_task_is_not_enough(self):
        record = ProviderTaskEvidence(
            repo_id=REPO,
            revision=REV,
            task="summarization",
            source="huggingface:revision-model-info",
            applicability="repository",
        )
        result = self.associate(task_records=(record,))
        self.assertEqual(result.status, "unknown")
        self.assertIn("task_applicability_not_artifact_scoped", result.reasons)

    def test_wrong_task_revision_is_rejected(self):
        record = ProviderTaskEvidence(
            repo_id=REPO,
            revision=OTHER_REV,
            task="summarization",
            source="huggingface:revision-model-info",
            applicability="artifact_file",
            file_name=FILE,
        )
        result = self.associate(task_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("task_revision_mismatch", result.reasons)

    def test_wrong_task_file_is_rejected(self):
        record = ProviderTaskEvidence(
            repo_id=REPO,
            revision=REV,
            task="summarization",
            source="huggingface:revision-model-info",
            applicability="artifact_file",
            file_name="other.gguf",
        )
        result = self.associate(task_records=(record,))
        self.assertEqual(result.status, "rejected")
        self.assertIn("task_file_mismatch", result.reasons)

    def test_conflicting_task_applicability_is_rejected(self):
        repository_record = ProviderTaskEvidence(
            repo_id=REPO,
            revision=REV,
            task="summarization",
            source="huggingface:revision-model-info",
            applicability="repository",
        )
        result = self.associate(
            task_records=(self.task_evidence, repository_record)
        )
        self.assertEqual(result.status, "rejected")
        self.assertIn("conflicting_provider_task_evidence", result.reasons)

    def test_unbound_identity_is_rejected(self):
        binding = UpstreamBindingResult(
            status="unbound",
            reasons=("no_provider_digest_match",),
        )
        result = self.associate(binding=binding)
        self.assertEqual(result.status, "rejected")
        self.assertIn("upstream_binding_unbound", result.reasons)

    def test_unknown_identity_stays_unknown(self):
        binding = UpstreamBindingResult(
            status="unknown",
            reasons=("local_blob_hash_not_available",),
        )
        result = self.associate(binding=binding)
        self.assertEqual(result.status, "unknown")
        self.assertIn("upstream_binding_unknown", result.reasons)

    def test_malformed_local_context_is_rejected_without_leaking_path(self):
        context = LocalArtifactTaskContext(
            model_id="/home/private/model",
            artifact_id="artifact",
            registry_identity="registry.ollama.ai/library/example/latest",
            manifest_digest=self.context.manifest_digest,
        )
        result = self.associate(context=context)
        self.assertEqual(result.status, "rejected")
        encoded = json.dumps(result.to_dict())
        self.assertNotIn("/home/private/model", encoded)

    def test_private_path_task_source_is_rejected_without_leaking_path(self):
        record = ProviderTaskEvidence(
            repo_id=REPO,
            revision=REV,
            task="summarization",
            source="/home/private/task-record",
            applicability="artifact_file",
            file_name=FILE,
        )
        result = self.associate(task_records=(record,))
        self.assertEqual(result.status, "rejected")
        encoded = json.dumps(result.to_dict())
        self.assertNotIn("/home/private/task-record", encoded)

    def test_association_does_not_promote_recommendation(self):
        associated = self.associate()
        self.assertEqual(associated.status, "associated")

        model = ModelIdentity(model_id="ollama:example", tasks=())
        artifact = ModelArtifact(
            artifact_id="artifact-1",
            model_id=model.model_id,
            location="local",
        )
        qualification = ModelQualification(
            model_id=model.model_id,
            artifact_id=artifact.artifact_id,
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
            UPSTREAM_FILE_DIGEST_TRUST_ROOT,
            recommendation.evidence_sources,
        )

    def test_model_profile_contract_is_unchanged(self):
        model = ModelIdentity(model_id="ollama:example")
        artifact = ModelArtifact(
            artifact_id="artifact-1",
            model_id=model.model_id,
        )
        self.assertNotIn("task_association", asdict(model))
        self.assertNotIn("task_association", asdict(artifact))

    def test_duplicate_identical_records_are_deterministic(self):
        result = self.associate(
            revision_files=(self.file_evidence, self.file_evidence),
            task_records=(self.task_evidence, self.task_evidence),
        )
        self.assertEqual(result.status, "associated")
        self.assertEqual(
            result.task_sources,
            ("huggingface:revision-model-info",),
        )


if __name__ == "__main__":
    unittest.main()
