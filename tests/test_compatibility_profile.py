import json
import unittest

from liongateos_model_advisor.compatibility_profile import (
    COMPATIBILITY_SCHEMA_VERSION,
    CompatibilityProfile,
    RuntimeCompatibility,
)


class CompatibilityProfileTests(unittest.TestCase):
    def test_profile_serializes_machine_readable_results(self):
        profile = CompatibilityProfile(
            hardware_schema_version="1",
            runtime_schema_version="1",
            runtimes=(
                RuntimeCompatibility(
                    runtime_name="ollama",
                    status="unknown",
                    reasons=("backend-capability-unknown",),
                    evidence_sources=("hardware-profile", "runtime-profile"),
                ),
                RuntimeCompatibility(
                    runtime_name="llama.cpp",
                    status="unavailable",
                    reasons=("runtime-not-discovered",),
                    evidence_sources=("runtime-profile",),
                ),
            ),
        )

        decoded = json.loads(json.dumps(profile.to_dict()))

        self.assertEqual(
            decoded["schema_version"],
            COMPATIBILITY_SCHEMA_VERSION,
        )
        self.assertEqual(decoded["hardware_schema_version"], "1")
        self.assertEqual(decoded["runtime_schema_version"], "1")
        self.assertEqual(decoded["runtimes"][0]["status"], "unknown")
        self.assertEqual(decoded["runtimes"][1]["status"], "unavailable")

    def test_unavailable_is_distinct_from_incompatible(self):
        result = RuntimeCompatibility(
            runtime_name="vllm",
            status="unavailable",
            reasons=("runtime-not-discovered",),
        )

        self.assertEqual(result.status, "unavailable")
        self.assertNotEqual(result.status, "incompatible")

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            RuntimeCompatibility(
                runtime_name="ollama",
                status="maybe",  # type: ignore[arg-type]
            )


if __name__ == "__main__":
    unittest.main()
