import json
import unittest

from liongateos_model_advisor.runtime_profile import (
    RUNTIME_SCHEMA_VERSION,
    Runtime,
    RuntimeProfile,
)


class RuntimeProfileTests(unittest.TestCase):
    def test_runtime_profile_serializes_to_json(self):
        profile = RuntimeProfile(
            runtimes=(
                Runtime(
                    name="ollama",
                    available=True,
                    version="0.22.1",
                    executables=("ollama",),
                    discovery_sources=("path",),
                ),
                Runtime(
                    name="llama.cpp",
                    available=True,
                    version="0.1.0-dev",
                    build="1",
                    commit="9d57ce4",
                    executables=("llama-cli", "llama-server"),
                    discovery_sources=("custom-path",),
                ),
            )
        )

        decoded = json.loads(json.dumps(profile.to_dict()))

        self.assertEqual(decoded["schema_version"], RUNTIME_SCHEMA_VERSION)
        self.assertEqual(decoded["runtimes"][0]["name"], "ollama")
        self.assertEqual(decoded["runtimes"][1]["commit"], "9d57ce4")
        self.assertNotIn("/home/", json.dumps(decoded))

    def test_unavailable_runtime_preserves_unknown_metadata(self):
        profile = RuntimeProfile(
            runtimes=(
                Runtime(
                    name="vllm",
                    available=False,
                    discovery_sources=("path",),
                ),
            )
        )

        data = profile.to_dict()["runtimes"][0]

        self.assertFalse(data["available"])
        self.assertIsNone(data["version"])
        self.assertEqual(data["executables"], ())


if __name__ == "__main__":
    unittest.main()
