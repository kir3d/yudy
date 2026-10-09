"""Small local GoTrue-compatible stub used by smoke.py."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


USER = {"id": "11111111-1111-4111-8111-111111111111", "email": "test@yudyai.xyz"}
SESSION = {
    "access_token": "local-access-token",
    "refresh_token": "refresh12345",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": USER,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/auth/v1/user" and self.headers.get("Authorization") == "Bearer local-access-token":
            self.send_json(200, USER)
            return
        self.send_json(401, {"message": "invalid token"})

    def do_POST(self):
        if self.path in {
            "/auth/v1/signup",
            "/auth/v1/token?grant_type=password",
            "/auth/v1/token?grant_type=refresh_token",
        }:
            self.send_json(200, SESSION)
            return
        if self.path == "/auth/v1/logout":
            self.send_response(204)
            self.end_headers()
            return
        self.send_json(404, {"message": "not found"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8790), Handler).serve_forever()
