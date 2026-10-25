"""Local HTTP server for the Kleene visual workbench.

Serves a small JSON API (compile / analyze / bench) plus the static web/
bundle.  Bound to 127.0.0.1 by default; the server only parses the pattern
and text posted in the request, never reads files.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__
from .ast import ParseError
from .bench import bench_all
from .engine import DOTALL, MULTILINE, IGNORECASE, Regex

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}

FLAG_LETTERS = {"i": IGNORECASE, "s": DOTALL, "m": MULTILINE}


def _flags(letters):
    f = 0
    for ch in letters or "":
        f |= FLAG_LETTERS.get(ch, 0)
    return f


def analyze(pattern, text, flags=""):
    rx = Regex(pattern, _flags(flags))
    matches = []
    for m in rx.finditer(text):
        matches.append({
            "match": m.group(0),
            "span": list(m.span(0)),
            "groups": m.groups(),
            "groupdict": m.to_dict(),
        })
    return {
        "explain": rx.explain(),
        "matches": matches,
        "nfa": rx.nfa_graph(),
        "dfa": rx.dfa_graph(),
        "trace": rx.trace(text),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = f"Kleene/{__version__}"

    def log_message(self, *args):
        pass

    # ---- helpers -----------------------------------------------------
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg, status=400):
        self._json({"error": str(msg)}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    # ---- routing -----------------------------------------------------
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/health":
            return self._json({"status": "ok", "version": __version__})
        return self._static(route)

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            if route == "/api/analyze":
                payload = self._read_body()
                pattern = payload.get("pattern", "")
                text = payload.get("text", "")
                flags = payload.get("flags", "")
                return self._json(analyze(pattern, text, flags))
            if route == "/api/bench":
                return self._json(bench_all())
            return self._error("unknown route", 404)
        except ParseError as exc:
            return self._error(str(exc), 422)
        except Exception as exc:  # surface, do not crash the server
            return self._error(str(exc), 500)

    # ---- static ------------------------------------------------------
    def _static(self, route):
        if route in ("", "/"):
            route = "/index.html"
        rel = route.lstrip("/")
        safe = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not safe.startswith(os.path.abspath(WEB_DIR)) or \
                not os.path.isfile(safe):
            return self._error("not found", 404)
        with open(safe, "rb") as fh:
            body = fh.read()
        ext = os.path.splitext(safe)[1].lower()
        self.send_response(200)
        self.send_header("Content-Type",
                         CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8856):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print("Kleene regex workbench")
    print(f"Dashboard: {url}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kleene workbench server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8856)
    args = parser.parse_args()
    serve(args.host, args.port)
