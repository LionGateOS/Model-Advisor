"""Conservative recommendation contract regression tests."""

import unittest

from liongateos_model_advisor.model_profile import (
    MetadataEvidence,
    ModelArtifact,
    ModelIdentity,
)
from liongateos_model_advisor.qualification import ModelQualification
from liongateos_model_advisor.recommendation import recommend_local_model


class RecommendationTests(unittest.TestCase):
    def make_inputs(
        self,
        *,
        tasks=("code-generation",),
        evidence=True,
        qualification_status="qualified",
        location="local",
    ):
        model = ModelIdentity(
            model_id="ollama:test",
            tasks=tasks,
            evidence=(
                MetadataEvidence(
                    field="tasks",
                    source="test:reported-tasks",
                    kind="reported",
                ),
            ) if evidence else (),
        )
        artifact = ModelArtifact(
            artifact_id="artifact-1",
            model_id="ollama:test",
            location=location,
        )
        qualification = ModelQualification(
            model_id="ollama:test",
            artifact_id="artifact-1",
            runtime_name="ollama",
            status=qualification_status,
            execution_path="single_gpu" if qualification_status == "qualified" else "unknown",
            evidence_sources=("test:runtime",),
        )
        return model, artifact, qualification

    def classify(self, **kwargs):
        model, artifact, qualification = self.make_inputs(**kwargs)
        return recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )

    def test_positive_workload_and_qualification(self):
        result = self.classify()
        self.assertEqual(result.status, "supported_candidate")
        self.assertIn("test:reported-tasks", result.evidence_sources)

    def test_unknown_hardware(self):
        result = self.classify(qualification_status="unknown")
        self.assertEqual(result.status, "needs_hardware_verification")

    def test_candidate_hardware(self):
        result = self.classify(qualification_status="candidate")
        self.assertEqual(result.status, "needs_hardware_verification")

    def test_not_qualified(self):
        result = self.classify(qualification_status="not_qualified")
        self.assertEqual(result.status, "not_recommended")

    def test_missing_workload_metadata(self):
        result = self.classify(tasks=())
        self.assertEqual(result.status, "workload_unknown")

    def test_unverified_workload_metadata(self):
        result = self.classify(evidence=False)
        self.assertEqual(result.status, "workload_unknown")

    def test_unrelated_capability_evidence_does_not_verify_task(self):
        model, artifact, qualification = self.make_inputs(evidence=False)
        model = ModelIdentity(
            model_id=model.model_id,
            tasks=("code-generation",),
            capabilities=("tools",),
            evidence=(
                MetadataEvidence(
                    field="capabilities",
                    source="test:reported-tools",
                    kind="reported",
                ),
            ),
        )
        result = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )
        self.assertEqual(result.status, "workload_unknown")

    def test_matching_reported_capability_is_accepted(self):
        model, artifact, qualification = self.make_inputs(evidence=False)
        model = ModelIdentity(
            model_id=model.model_id,
            capabilities=("code-generation",),
            evidence=(
                MetadataEvidence(
                    field="capabilities",
                    source="test:reported-code-generation",
                    kind="reported",
                ),
            ),
        )
        result = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )
        self.assertEqual(result.status, "supported_candidate")

    def test_ollama_generic_capabilities_do_not_prove_coding(self):
        model, artifact, qualification = self.make_inputs(evidence=False)
        model = ModelIdentity(
            model_id=model.model_id,
            capabilities=("completion", "thinking", "tools"),
            evidence=(
                MetadataEvidence(
                    field="capabilities",
                    source="test:ollama-capabilities",
                    kind="reported",
                ),
            ),
        )
        result = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="coding",
        )
        self.assertEqual(result.status, "workload_unknown")

    def test_embedding_only_does_not_prove_chat(self):
        model, artifact, qualification = self.make_inputs(evidence=False)
        model = ModelIdentity(
            model_id=model.model_id,
            capabilities=("embedding",),
            evidence=(
                MetadataEvidence(
                    field="capabilities",
                    source="test:ollama-embedding",
                    kind="reported",
                ),
            ),
        )
        result = recommend_local_model(
            model=model,
            artifact=artifact,
            qualification=qualification,
            workload="general_chat",
        )
        self.assertEqual(result.status, "workload_unknown")

    def test_remote_artifact_rejected(self):
        model, artifact, qualification = self.make_inputs(location="remote")
        with self.assertRaises(ValueError):
            recommend_local_model(
                model=model,
                artifact=artifact,
                qualification=qualification,
                workload="coding",
            )

    def test_unknown_workload_rejected(self):
        model, artifact, qualification = self.make_inputs()
        with self.assertRaises(ValueError):
            recommend_local_model(
                model=model,
                artifact=artifact,
                qualification=qualification,
                workload="fictional",
            )

    def test_identity_mismatch_rejected(self):
        model, artifact, qualification = self.make_inputs()
        artifact = ModelArtifact(
            artifact_id="different",
            model_id=model.model_id,
            location="local",
        )
        with self.assertRaises(ValueError):
            recommend_local_model(
                model=model,
                artifact=artifact,
                qualification=qualification,
                workload="coding",
            )

    def test_no_performance_score(self):
        result = self.classify().to_dict()
        self.assertNotIn("score", result)
        self.assertNotIn("performance", result)


if __name__ == "__main__":
    unittest.main()
