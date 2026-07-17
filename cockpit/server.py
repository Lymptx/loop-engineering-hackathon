"""Small standard-library HTTP server for the live cockpit."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cockpit import demo, store, subject_view

_STATIC_DIR = Path(__file__).parent / "static"
_DEMO_THREAD: threading.Thread | None = None
_STOP_EVENT = threading.Event()
_THREAD_LOCK = threading.Lock()


class CockpitHandler(BaseHTTPRequestHandler):
    server_version = "AgentImmuneCockpit/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self._send_file(_STATIC_DIR / "index.html")
            return
        if path.startswith("/static/"):
            self._send_file(_STATIC_DIR / path.removeprefix("/static/"))
            return
        if path == "/api/demo/state":
            self._send_json(store.state())
            return
        if path == "/api/demo/events":
            after = int(parse_qs(parsed.query).get("after", ["0"])[0])
            events = [e for e in store.events() if e["sequence"] > after]
            self._send_json({"events": events})
            return
        if path == "/api/demo/attacker-bundles":
            self._send_json({"attack_bundles": store.attack_bundles()})
            return
        if path == "/api/demo/defender-bundles":
            self._send_json({"defender_bundles": store.defender_bundles()})
            return
        if path == "/api/demo/generation-history":
            self._send_json({"generation_history": store.history()})
            return
        if path == "/api/demo/metrics":
            self._send_json({"metrics": store.metrics()})
            return
        if path == "/api/demo/target-agent":
            self._send_json(subject_view.snapshot())
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/demo/reset":
            _stop_demo_thread()
            demo.reset_demo()
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/demo/start":
            payload = self._read_json()
            pace = float(payload.get("pace_seconds", 0.35))
            status = _start_demo_thread(pace)
            self._send_json(status)
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[cockpit] {self.address_string()} - {fmt % args}")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: dict, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _start_demo_thread(pace_seconds: float) -> dict:
    global _DEMO_THREAD, _STOP_EVENT
    with _THREAD_LOCK:
        if _DEMO_THREAD and _DEMO_THREAD.is_alive():
            return {"ok": True, "status": "already_running", "run_id": demo.RUN_ID}
        _STOP_EVENT = threading.Event()

        def target() -> None:
            demo.run_next_step(
                pace_seconds=pace_seconds,
                stop_event=_STOP_EVENT,
            )

        _DEMO_THREAD = threading.Thread(target=target, name="cockpit-demo", daemon=True)
        _DEMO_THREAD.start()
        return {"ok": True, "status": "started", "run_id": demo.RUN_ID}


def _stop_demo_thread() -> None:
    with _THREAD_LOCK:
        _STOP_EVENT.set()


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), CockpitHandler)
    print(f"Live cockpit: http://{host}:{port}")
    print("Press Start Demo in the browser to run the deterministic loop.")
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent-immune-cockpit")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
