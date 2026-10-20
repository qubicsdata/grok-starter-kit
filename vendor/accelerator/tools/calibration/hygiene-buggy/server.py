"""Seeded defects: hardcoded secret, hardcoded host:port, ad-hoc error statuses."""
import json
from http.server import BaseHTTPRequestHandler

API_KEY = "example_live_abc123def456ghi"          # H3: hardcoded credential literal
BASE = "http://localhost:8000"                # H4: hardcoded host:port


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/ok":
            # Ad-hoc error responses, no shared error builder (H5).
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()

    def do_POST(self) -> None:
        if not self.path:
            self.send_response(400)
            self.end_headers()
            return
        self.send_response(201)
        self.end_headers()
        json.dumps({"ok": True})
