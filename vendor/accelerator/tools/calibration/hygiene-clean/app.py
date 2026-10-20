"""A minimal, hygienic HTTP handler: shared error builder, env config, no secrets."""
import json
from http.server import BaseHTTPRequestHandler

from config import PORT  # noqa: F401  (config comes from env)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_error("NOT_FOUND", "no such route")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: str, message: str) -> None:
        # One shared error schema for every failure path.
        self._send_json(404, {"error": {"code": code, "message": message}})
