import json
import unittest

from liongateos_model_advisor.model_profile import (
    MODEL_SCHEMA_VERSION,
    MetadataEvidence,
    ModelArtifact,
    ModelIdentity,
    ModelProfile,
    ModelSourceStatus,
)


class ModelProfileTests(unittest.TestCase):
    def test_profile_serializes_model_and_artifact_metadata(self):
        profile = ModelProfile(
            models=(
                ModelIdentity(
                    model_id="example/model-27b",
                    display_name="Example 27B",
                    family="example",
                    architecture="example-architecture",
                    parameter_count=27_000_000_000,
                    context_length=131_072,
                    tasks=("text-generation",),
                    license="apache-2.0",
                    evidence=(
                        MetadataEvidence(
                            field="parameter_count",
                            source="upstream-model-metadata",
                            kind="reported",
                        ),
                    ),
                ),
            ),
            artifacts=(
                ModelArtifact(
                    artifact_id="example/model-27b:gguf-q8_0",
                    model_id="example/model-27b",
                    format="gguf",
                    quantization="Q8_0",
                    size_bytes=28_000_000_000,
                    evidence=(
                        MetadataEvidence(
                            field="quantization",
                            source="gguf-metadata",
                            kind="reported",
                        ),
                    ),
                ),
            ),
        )

        decoded = json.loads(json.dumps(profile.to_dict()))

        self.assertEqual(decoded["schema_version"], MODEL_SCHEMA_VERSION)
        self.assertEqual(
            decoded["models"][0]["parameter_count"],
            27_000_000_000,
        )
        self.assertEqual(
            decoded["artifacts"][0]["quantization"],
            "Q8_0",
        )
        self.assertEqual(
            decoded["artifacts"][0]["evidence"][0]["kind"],
            "reported",
        )

    def test_unknown_values_remain_unknown(self):
        profile = ModelProfile(
            models=(
                ModelIdentity(
                    model_id="example/unknown-model",
                ),
            ),
        )

        model = profile.to_dict()["models"][0]

        self.assertIsNone(model["parameter_count"])
        self.assertIsNone(model["active_parameter_count"])
        self.assertIsNone(model["context_length"])
        self.assertIsNone(model["license"])

    def test_assumptions_are_explicit_evidence(self):
        evidence = MetadataEvidence(
            field="context_length",
            source="advisor-fallback-rule",
            kind="assumed",
        )

        self.assertEqual(evidence.kind, "assumed")

    def test_invalid_evidence_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            MetadataEvidence(
                field="parameter_count",
                source="example-source",
                kind="guess",  # type: ignore[arg-type]
            )

    def test_invalid_model_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            ModelIdentity(
                model_id="example/model",
                parameter_count=7_000_000_000,
                active_parameter_count=8_000_000_000,
            )

    def test_invalid_artifact_location_is_rejected(self):
        with self.assertRaises(ValueError):
            ModelArtifact(
                artifact_id="example:model",
                model_id="example/model",
                location="somewhere",  # type: ignore[arg-type]
            )

    def test_invalid_model_source_status_is_rejected(self):
        with self.assertRaises(ValueError):
            ModelSourceStatus(
                source="example-source",
                status="guess",  # type: ignore[arg-type]
            )

    def test_artifact_must_reference_known_model(self):
        with self.assertRaises(ValueError):
            ModelProfile(
                artifacts=(
                    ModelArtifact(
                        artifact_id="example:gguf-q4",
                        model_id="missing/model",
                        format="gguf",
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
