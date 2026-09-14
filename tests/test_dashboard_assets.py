import unittest
import threading
from urllib.request import urlopen

from liongateos_model_advisor.dashboard_server import (
    create_dashboard_server,
)


class DashboardAssetTests(unittest.TestCase):
    def setUp(self):
        self.server = create_dashboard_server(port=0)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def read(self, path):
        with urlopen(
            f"{self.base_url}{path}",
            timeout=2,
        ) as response:
            return response, response.read().decode("utf-8")

    def test_root_serves_dashboard_shell_with_security_headers(self):
        response, body = self.read("/")

        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertEqual(
            response.headers["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertEqual(
            response.headers["X-Frame-Options"],
            "DENY",
        )
        self.assertIn(
            "default-src 'self'",
            response.headers["Content-Security-Policy"],
        )
        self.assertIn("LionGateOS Model Advisor", body)
        self.assertIn('id="runtime-list"', body)
        self.assertIn('id="model-list"', body)
        self.assertIn('id="model-summary"', body)
        self.assertIn('id="ecosystem-list"', body)
        self.assertIn('id="ecosystem-summary"', body)

    def test_theme_exposes_semantic_liongateos_tokens(self):
        response, body = self.read("/theme.css")

        self.assertEqual(response.status, 200)

        for token in (
            "--lg-bg",
            "--lg-surface",
            "--lg-text",
            "--lg-text-muted",
            "--lg-border",
            "--lg-accent",
            "--lg-success",
            "--lg-warning",
            "--lg-danger",
            "--lg-info",
            "--lg-focus",
        ):
            self.assertIn(token, body)

    def test_dashboard_script_uses_read_only_api(self):
        response, body = self.read("/dashboard.js")

        self.assertEqual(response.status, 200)
        self.assertIn('fetch("/api/dashboard"', body)
        self.assertIn("Why / Evidence", body)
        self.assertIn("renderModels", body)
        self.assertIn("renderEcosystem", body)
        self.assertIn("Hugging Face", body)
        self.assertIn("OpenRouter", body)
        self.assertIn("Metadata evidence", body)
        self.assertIn("Not locally stored", body)
        self.assertIn("Same as exact count", body)
        self.assertIn("formatSizeLabel", body)
        self.assertIn("artifact.location", body)
        self.assertIn("inventory partial", body)
        self.assertIn("Ollama metadata source unavailable", body)
        self.assertIn("Ollama metadata source error", body)
        self.assertNotIn("innerHTML", body)


if __name__ == "__main__":
    unittest.main()
