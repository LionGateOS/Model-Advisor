"""Loopback-only HTTP server for the LionGateOS Model Advisor dashboard."""

from __future__ import annotations

import json
from collections.abc import Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from .dashboard import collect_dashboard_data


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/theme.css": ("theme.css", "text/css; charset=utf-8"),
    "/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
    "/dashboard.js": ("dashboard.js", "text/javascript; charset=utf-8"),
}


class DashboardHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying only the dashboard's approved runtime paths."""

    def __init__(
        self,
        server_address: tuple[str, int],
        runtime_paths: Sequence[str] | None = None,
    ) -> None:
        self.runtime_paths = tuple(runtime_paths or ())
        super().__init__(server_address, DashboardRequestHandler)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Serve the dashboard's small read-only API and known static assets."""

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "frame-ancestors 'none'",
        )

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(
            status,
            body,
            "application/json; charset=utf-8",
        )

    def _send_static(self, asset_name: str, content_type: str) -> None:
        asset = (
            files("liongateos_model_advisor")
            .joinpath("web")
            .joinpath(asset_name)
        )

        try:
            body = asset.read_bytes()
        except (FileNotFoundError, OSError):
            self._send_json(404, {"error": "not_found"})
            return

        self._send_bytes(200, body, content_type)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path

        if path == "/api/dashboard":
            data = collect_dashboard_data(self.server.runtime_paths)
            self._send_json(200, data)
            return

        asset = _STATIC_ASSETS.get(path)
        if asset is not None:
            self._send_static(*asset)
            return

        self._send_json(404, {"error": "not_found"})


def create_dashboard_server(
    runtime_paths: Sequence[str] | None = None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> DashboardHTTPServer:
    """Create the loopback-only read-only dashboard server."""

    if host != DEFAULT_HOST:
        raise ValueError(
            "dashboard host must remain on the loopback interface "
            f"{DEFAULT_HOST}"
        )

    return DashboardHTTPServer(
        (host, port),
        runtime_paths=runtime_paths,
    )
