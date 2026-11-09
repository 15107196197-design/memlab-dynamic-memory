"""Local web server for the dynamic memory workbench.

    python server.py            # http://127.0.0.1:8765
"""
import json
import mimetypes
import os
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from memlab import webapp
from memwb import config, dataset, export, memory, pipeline

MAX_ASK_BYTES = 100_000
MAX_IMPORT_BYTES = 20_000_000


def sample_from(args):
    return dataset.store().get(args.get("sample", [""])[0])


def questions(sample):
    return [{"index": i, "question": q.get("question"), "answer": q.get("answer"), "category": q.get("category"),
             "evidence": q.get("evidence", [])} for i, q in enumerate(sample.get("qa", [])) if q.get("question")]


def evaluation():
    path = config.EVAL_DIR / "results.json"
    if not path.exists():
        return {"available": False}
    return {"available": True, **json.loads(path.read_text(encoding="utf-8"))}


ROUTES = {
    "/api/samples": lambda args: [export.summary(s) for s in dataset.store().samples],
    "/api/memories": lambda args: dict(zip(("turns", "facts"), memory.build(sample_from(args)))),
    "/api/slots": lambda args: export.slots_table(sample_from(args)["sample_id"], memory.build(sample_from(args))[1]),
    "/api/questions": lambda args: questions(sample_from(args)),
    "/api/export": lambda args: export.export(sample_from(args)),
    "/api/evaluation": lambda args: evaluation(),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "MemoryWorkbench/1.0"

    def log_message(self, fmt, *args):
        if os.getenv("MEMORY_HTTP_LOG") == "1":
            super().log_message(fmt, *args)

    def send_json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path):
        data = path.read_bytes()
        kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith("javascript"):
            kind += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        try:
            args = parse_qs(url.query)
            if url.path.startswith("/api/v2/"):
                return self.send_json(webapp.get(url.path, args))
            if url.path in ROUTES:
                return self.send_json(ROUTES[url.path](args))
            name = "index.html" if url.path == "/" else url.path.lstrip("/")
            target = (config.WEB_DIR / name).resolve()
            if config.WEB_DIR.resolve() in target.parents and target.is_file():
                return self.send_file(target)
            self.send_json({"error": "not found"}, 404)
        except webapp.ModelUnavailableError as exc:
            self.send_json({"error": exc.as_payload()}, exc.status)
        except webapp.WebError as exc:
            self.send_json({"error": str(exc), **exc.details}, exc.status)
        except KeyError as exc:
            self.send_json({"error": str(exc).strip("'\"")}, 404)
        except Exception as exc:  # noqa: BLE001 - report to the client, keep serving
            traceback.print_exc()
            self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        try:
            if not (self.path in ("/api/ask", "/api/import") or self.path.startswith("/api/v2/")):
                return self.send_json({"error": "not found"}, 404)
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                # Local acceptance uses `curl -d '{...}'`, which defaults to
                # application/x-www-form-urlencoded while the body is still JSON.
                # Keep the strict check for legacy /api/* endpoints.
                if not (self.path.startswith("/api/v2/")
                        and content_type in ("application/x-www-form-urlencoded", "")):
                    return self.send_json({"error": "Expected application/json"}, 415)
            length = int(self.headers.get("Content-Length", "0"))
            limit = MAX_IMPORT_BYTES if self.path == "/api/import" else MAX_ASK_BYTES
            if length <= 0 or length > limit:
                raise ValueError("Request size out of bounds")
            body = json.loads(self.rfile.read(length))
            if self.path.startswith("/api/v2/"):
                return self.send_json(webapp.post(self.path, body))
            if self.path == "/api/import":
                return self.send_json({"imported": dataset.store().import_samples(body)})
            k = min(50, max(1, int(body.get("k", 15))))
            self.send_json(pipeline.answer(body["sample"], body.get("question", ""), body.get("method", "dynamic"), k, body.get("as_of") or None))
        except webapp.ModelUnavailableError as exc:
            self.send_json({"error": exc.as_payload()}, exc.status)
        except webapp.WebError as exc:
            self.send_json({"error": str(exc), **exc.details}, exc.status)
        except KeyError as exc:
            self.send_json({"error": "Missing or unknown: " + str(exc).strip("'\"")}, 400)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.send_json({"error": str(exc)}, 500)


def main():
    port = int(os.getenv("MEMORY_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Open http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
