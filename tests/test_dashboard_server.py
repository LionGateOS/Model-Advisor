import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from liongateos_model_advisor.dashboard_server import (
    DEFAULT_HOST,
    create_dashboard_server,
)


class DashboardServerTests(unittest.TestCase):
    def test_default_host_is_loopback(self):
        server = create_dashboard_server(port=0)
        try:
            self.assertEqual(
                server.server_address[0],
                DEFAULT_HOST,
            )
            self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        finally:
            server.server_close()

    def test_non_loopback_host_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "loopback interface",
        ):
            create_dashboard_server(
                host="0.0.0.0",
                port=0,
            )

    @patch(
        "liongateos_model_advisor.dashboard_server.collect_dashboard_data"
    )
    def test_dashboard_endpoint_returns_collected_data(self, collect):
        collect.return_value = {
            "hardware": {"schema_version": "1"},
            "runtimes": {"schema_version": "1"},
            "compatibility": {"schema_version": "1"},
        }

        server = create_dashboard_server(
            ["/private/example/llama.cpp/bin"],
            port=0,
        )
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        try:
            host, port = server.server_address
            with urlopen(
                f"http://{host}:{port}/api/dashboard",
                timeout=2,
            ) as response:
                data = json.loads(
                    response.read().decode("utf-8")
                )

            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers["Cache-Control"],
                "no-store",
            )
            self.assertEqual(
                data["compatibility"]["schema_version"],
                "1",
            )
            collect.assert_called_once_with(
                ("/private/example/llama.cpp/bin",)
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_unknown_path_is_not_served(self):
        server = create_dashboard_server(port=0)
        thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
        )
        thread.start()

        try:
            host, port = server.server_address

            with self.assertRaises(HTTPError) as context:
                urlopen(
                    f"http://{host}:{port}/private-file",
                    timeout=2,
                )

            self.assertEqual(context.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
