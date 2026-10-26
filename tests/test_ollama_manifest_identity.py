import json
import tempfile
import unittest
from pathlib import Path

from liongateos_model_advisor.ollama_manifest_identity import (
    discover_registry_identity,
)


class OllamaManifestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifests = self.root / "manifests"
        self.blobs = self.root / "blobs"
        self.manifests.mkdir()
        self.blobs.mkdir()
        self.model_digest = "a" * 64
        self.model_blob = self.blobs / ("sha256-" + self.model_digest)
        self.model_blob.write_bytes(b"model-data")

    def tearDown(self):
        self.temp.cleanup()

    def add_manifest(self, relative_path, *, digest=None, size=10, layers=None):
        path = self.manifests / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if layers is None:
            layers = [{
                "mediaType": "application/vnd.ollama.image.model",
                "digest": "sha256:" + (digest or self.model_digest),
                "size": size,
            }]
        path.write_text(json.dumps({"schemaVersion": 2, "layers": layers}))
        return path

    def test_exact_default_library_manifest_and_blob(self):
        self.add_manifest("registry.ollama.ai/library/example/latest")
        self.assertEqual(
            discover_registry_identity(
                "example:latest", models_roots=(self.root,)
            ),
            "registry.ollama.ai/library/example/latest",
        )

    def test_namespaced_registration(self):
        self.add_manifest("registry.ollama.ai/team/example/v2")
        self.assertEqual(
            discover_registry_identity("team/example:v2", models_roots=(self.root,)),
            "registry.ollama.ai/team/example/v2",
        )

    def test_missing_manifest_is_unknown(self):
        self.assertIsNone(
            discover_registry_identity("missing:latest", models_roots=(self.root,))
        )

    def test_malformed_manifest_is_unknown(self):
        path = self.manifests / "registry.ollama.ai/library/example/latest"
        path.parent.mkdir(parents=True)
        path.write_text("{broken")
        self.assertIsNone(
            discover_registry_identity("example:latest", models_roots=(self.root,))
        )

    def test_missing_or_wrong_sized_blob_is_unknown(self):
        self.add_manifest("registry.ollama.ai/library/example/latest", size=99)
        self.assertIsNone(
            discover_registry_identity("example:latest", models_roots=(self.root,))
        )

    def test_ambiguous_registry_matches_are_unknown(self):
        self.add_manifest("registry.ollama.ai/library/example/latest")
        self.add_manifest("mirror.example/library/example/latest")
        self.assertIsNone(
            discover_registry_identity("example:latest", models_roots=(self.root,))
        )

    def test_invalid_registration_name_is_unknown(self):
        self.assertIsNone(
            discover_registry_identity("../example:latest", models_roots=(self.root,))
        )

    def test_manifest_without_one_model_layer_is_unknown(self):
        self.add_manifest(
            "registry.ollama.ai/library/example/latest",
            layers=[],
        )
        self.assertIsNone(
            discover_registry_identity("example:latest", models_roots=(self.root,))
        )


if __name__ == "__main__":
    unittest.main()
