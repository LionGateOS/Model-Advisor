import unittest
import threading
from urllib.request import urlopen

from liongateos_model_advisor.dashboard_server import (
    create_dashboard_server,
)


class DashboardAssetTests(unittest.TestCase):

    def test_missing_evidence_has_explanations(self):
        from importlib.resources import files

        script = files("liongateos_model_advisor").joinpath(
            "web", "dashboard.js"
        ).read_text()

        for expected in (
            "Dedicated VRAM not reported",
            "Driver version not reported",
            "Runtime not detected through configured discovery paths",
            "Not estimated",
            "Not assessed",
            "Not reported by source",
            "No verified model link",
        ):
            self.assertIn(expected, script)

        self.assertNotIn('addMeta(meta, "Build", runtime.build)', script)
        self.assertNotIn('addMeta(meta, "Commit", runtime.commit)', script)



    def test_dashboard_has_accessible_section_tabs(self):
        from importlib.resources import files
        html = files("liongateos_model_advisor").joinpath(
            "web", "index.html"
        ).read_text()
        script = files("liongateos_model_advisor").joinpath(
            "web", "dashboard.js"
        ).read_text()
        for name in (
            "overview", "hardware", "runtimes",
            "models", "context", "ecosystem"
        ):
            self.assertIn(f'id="tab-{name}"', html)
            self.assertIn(f'id="panel-{name}"', html)
        self.assertIn('role="tablist"', html)
        self.assertIn('role="tabpanel"', html)
        self.assertIn("function activateDashboardTab", script)
        self.assertIn('event.key === "ArrowRight"', script)


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
        self.assertIn('id="context-comparison"', body)
        self.assertIn('id="ecosystem-list"', body)
        self.assertIn('id="ecosystem-summary"', body)

    def test_model_suitability_statuses_have_distinct_styles(self):
        _, script = self.read("/dashboard.js")
        _, css = self.read("/dashboard.css")

        for status in ("qualified", "candidate", "not_qualified", "unknown"):
            self.assertIn(status, script)

        self.assertIn('status === "not_qualified" ? "incompatible" : status', script)
        self.assertIn(".status-qualified", css)
        self.assertIn(".status-candidate", css)
        self.assertIn("var(--lg-success)", css)
        self.assertIn("var(--lg-warning)", css)

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
        self.assertIn('fetch(force ? "/api/dashboard?refresh=1" : "/api/dashboard"', body)
        self.assertIn("Why / Evidence", body)
        self.assertIn("renderModels", body)
        self.assertIn("renderEcosystem", body)
        self.assertIn("Hugging Face", body)
        self.assertIn("OpenRouter", body)
        self.assertIn("Metadata evidence", body)
        self.assertIn("Not locally stored", body)
        self.assertIn("Same as exact count", body)
        self.assertIn("formatSizeLabel", body)
        self.assertIn("context-model-selector", body)
        self.assertIn("Context limit", body)
        self.assertIn("Total memory fit", body)
        self.assertIn("artifact.location", body)
        self.assertIn("inventory partial", body)
        self.assertIn("Ollama metadata source unavailable", body)
        self.assertIn("Ollama metadata source error", body)
        self.assertNotIn("innerHTML", body)


if __name__ == "__main__":
    unittest.main()
