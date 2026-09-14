import json
import unittest

from liongateos_model_advisor.model_profile import (
    MODEL_SCHEMA_VERSION,
    MetadataEvidence,
    ModelArtifact,
    ModelIdentity,
    ModelOffering,
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

    def test_layerwise_attention_geometry_is_preserved(self):
        profile = ModelProfile(
            models=(
                ModelIdentity(
                    model_id="example/layerwise",
                    block_count=4,
                    attention_head_count=16,
                    attention_head_count_kv=(4, 4, 2, 2),
                    attention_key_length=128,
                    attention_value_length=128,
                ),
            ),
        )

        model = json.loads(json.dumps(profile.to_dict()))["models"][0]

        self.assertEqual(model["block_count"], 4)
        self.assertEqual(
            model["attention_head_count_kv"],
            [4, 4, 2, 2],
        )

    def test_layerwise_geometry_must_match_block_count(self):
        with self.assertRaises(ValueError):
            ModelIdentity(
                model_id="example/bad-layerwise",
                block_count=3,
                attention_head_count_kv=(4, 4),
            )

    def test_hybrid_memory_topology_is_preserved(self):
        profile = ModelProfile(
            models=(
                ModelIdentity(
                    model_id="example/hybrid",
                    block_count=5,
                    nextn_predict_layers=1,
                    full_attention_interval=4,
                    attention_recurrent_layers=(
                        True,
                        True,
                        True,
                        False,
                        False,
                    ),
                    ssm_conv_kernel=4,
                    ssm_group_count=16,
                    ssm_inner_size=6144,
                    ssm_state_size=128,
                    ssm_time_step_rank=48,
                ),
            ),
        )

        model = profile.to_dict()["models"][0]

        self.assertEqual(model["nextn_predict_layers"], 1)
        self.assertEqual(model["full_attention_interval"], 4)
        self.assertEqual(
            model["attention_recurrent_layers"],
            (True, True, True, False, False),
        )
        self.assertEqual(model["ssm_state_size"], 128)

    def test_nextn_layers_cannot_exceed_block_count(self):
        with self.assertRaises(ValueError):
            ModelIdentity(
                model_id="example/bad-mtp",
                block_count=4,
                nextn_predict_layers=5,
            )

    def test_recurrent_layer_map_must_match_block_count(self):
        with self.assertRaises(ValueError):
            ModelIdentity(
                model_id="example/bad-recurrent-map",
                block_count=4,
                attention_recurrent_layers=(True, False),
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

    def test_hosted_offering_serializes(self):
        profile = ModelProfile(
            models=(ModelIdentity(model_id="example/model"),),
            offerings=(
                ModelOffering(
                    offering_id="openrouter:example/model",
                    source="openrouter-api",
                    provider_model_id="example/model",
                    model_id="example/model",
                    context_length=131_072,
                    input_modalities=("text",),
                    output_modalities=("text",),
                    supported_parameters=("temperature", "top_p"),
                ),
            ),
        )

        offering = profile.to_dict()["offerings"][0]
        self.assertEqual(offering["source"], "openrouter-api")
        self.assertEqual(offering["context_length"], 131_072)

    def test_unlinked_hosted_offering_is_allowed(self):
        profile = ModelProfile(
            offerings=(
                ModelOffering(
                    offering_id="openrouter:provider-only",
                    source="openrouter-api",
                    provider_model_id="provider-only",
                ),
            ),
        )
        self.assertIsNone(profile.offerings[0].model_id)

    def test_offering_link_must_reference_known_model(self):
        with self.assertRaises(ValueError):
            ModelProfile(
                offerings=(
                    ModelOffering(
                        offering_id="openrouter:missing",
                        source="openrouter-api",
                        provider_model_id="missing",
                        model_id="missing/model",
                    ),
                ),
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
