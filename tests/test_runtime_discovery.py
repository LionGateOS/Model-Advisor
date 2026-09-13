import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from liongateos_model_advisor.runtime_discovery import (
    _discover_llama_cpp,
    _discover_ollama,
    _discover_vllm,
    discover_runtimes,
)


class RuntimeDiscoveryTests(unittest.TestCase):
    @patch("liongateos_model_advisor.runtime_discovery._run_version")
    @patch("liongateos_model_advisor.runtime_discovery.shutil.which")
    def test_discovers_ollama_from_path(self, which, run_version):
        which.return_value = "/usr/local/bin/ollama"
        run_version.return_value = "ollama version is 0.22.1"

        runtime = _discover_ollama()

        self.assertTrue(runtime.available)
        self.assertEqual(runtime.version, "0.22.1")
        self.assertEqual(runtime.executables, ("ollama",))
        self.assertNotIn("/usr/local", str(runtime))

    @patch("liongateos_model_advisor.runtime_discovery._run_version")
    @patch("liongateos_model_advisor.runtime_discovery.shutil.which")
    def test_vllm_ignores_warning_noise(self, which, run_version):
        which.return_value = "/example/vllm"
        run_version.return_value = (
            "WARNING detected different devices\n"
            "0.19.0"
        )

        runtime = _discover_vllm()

        self.assertTrue(runtime.available)
        self.assertEqual(runtime.version, "0.19.0")

    @patch("liongateos_model_advisor.runtime_discovery._run_version")
    @patch("liongateos_model_advisor.runtime_discovery.shutil.which")
    def test_llama_cpp_custom_directory(self, which, run_version):
        which.return_value = None
        run_version.return_value = (
            "version: 0.1.0-dev (build 1, commit 9d57ce4)\n"
            "built with GNU for Linux x86_64"
        )

        with TemporaryDirectory() as directory:
            for name in ("llama-cli", "llama-server"):
                path = Path(directory) / name
                path.write_text("#!/bin/sh\n", encoding="utf-8")
                path.chmod(0o755)

            runtime = _discover_llama_cpp([directory])

        self.assertTrue(runtime.available)
        self.assertEqual(runtime.version, "0.1.0-dev")
        self.assertEqual(runtime.build, "1")
        self.assertEqual(runtime.commit, "9d57ce4")
        self.assertEqual(
            runtime.executables,
            ("llama-cli", "llama-server"),
        )
        self.assertEqual(runtime.discovery_sources, ("custom-path",))
        self.assertNotIn(directory, str(runtime))

    @patch("liongateos_model_advisor.runtime_discovery.shutil.which")
    def test_missing_runtime_is_reported_unavailable(self, which):
        which.return_value = None

        profile = discover_runtimes()

        self.assertEqual(
            [runtime.name for runtime in profile.runtimes],
            ["ollama", "llama.cpp", "vllm"],
        )
        self.assertTrue(
            all(not runtime.available for runtime in profile.runtimes)
        )


if __name__ == "__main__":
    unittest.main()
