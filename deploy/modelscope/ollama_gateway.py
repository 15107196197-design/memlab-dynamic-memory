#!/usr/bin/env python3
"""Token-prefixed HTTP gateway in front of a local Ollama server.

The ModelScope Studio runs on someone else's free CPU instance and needs the
project's own Ollama (27B) on the GPU box, but Ollama must stay bound to
127.0.0.1 so the internet cannot use the GPU.  MemLab's Ollama client has no
header support, so the shared secret travels as the first path segment:

    OLLAMA_URL=https://<public-host>/<token>       in the Studio
    client asks   https://<public-host>/<token>/api/chat
    gateway calls http://127.0.0.1:11434/api/chat   and streams the reply back

Usage:
    GATEWAY_TOKEN=... python3 ollama_gateway.py --port 11500
    python3 ollama_gateway.py --port 11500 --token-file ~/.ollama_gateway_token

Everything is standard library only; no extra dependency on the GPU host.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import pathlib
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM_HOST = os.getenv("OLLAMA_UPSTREAM_HOST", "127.0.0.1")
UPSTREAM_PORT = int(os.getenv("OLLAMA_UPSTREAM_PORT", "11434"))
UPSTREAM_TIMEOUT = float(os.getenv("OLLAMA_UPSTREAM_TIMEOUT", "900"))
TOKEN = ""


class Gateway(BaseHTTPRequestHandler):
    server_version = "MemLabOllamaGateway/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(
            "%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), fmt % args)
        )

    def _secret_ok(self) -> bool:
        path = self.path
        prefix = "/" + TOKEN
        if not path.startswith(prefix + "/") and path != prefix:
            return False
        return True

    def _upstream_path(self) -> str:
        path = self.path[len("/" + TOKEN):]
        return path or "/"

    def _reject(self) -> None:
        body = json.dumps({"error": "unauthorized"}).encode()
        self.send_response(404 if self.command == "GET" else 403)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _forward(self) -> None:
        if not self._secret_ok():
            return self._reject()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() in ("content-type", "accept", "accept-encoding")
        }
        headers["Host"] = f"{UPSTREAM_HOST}:{UPSTREAM_PORT}"
        try:
            conn = http.client.HTTPConnection(
                UPSTREAM_HOST, UPSTREAM_PORT, timeout=UPSTREAM_TIMEOUT
            )
            conn.request(self.command, self._upstream_path(), body=body, headers=headers)
            upstream = conn.getresponse()
        except OSError as exc:
            message = json.dumps({"error": f"upstream unavailable: {exc}"}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
            return

        self.send_response(upstream.status)
        for key, value in upstream.getheaders():
            if key.lower() in ("transfer-encoding", "connection", "content-length"):
                continue
            self.send_header(key, value)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                self.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            conn.close()

    do_GET = _forward
    do_POST = _forward


def main() -> int:
    global TOKEN
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11500)
    parser.add_argument("--token-file", type=pathlib.Path, default=None)
    args = parser.parse_args()

    token = os.getenv("GATEWAY_TOKEN", "").strip()
    if not token and args.token_file:
        token = args.token_file.read_text().strip()
    if len(token) < 16:
        parser.error("need GATEWAY_TOKEN or --token-file with at least 16 characters")
    TOKEN = token

    server = ThreadingHTTPServer((args.host, args.port), Gateway)
    server.daemon_threads = True
    print(f"gateway on http://{args.host}:{args.port}/<token> -> "
          f"http://{UPSTREAM_HOST}:{UPSTREAM_PORT}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
