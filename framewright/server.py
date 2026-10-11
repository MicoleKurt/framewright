"""Web UI + JSON API (stdlib only). `framewright serve` -> http://localhost:8000"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import brands, relevance, render, voice
from .formats import FORMATS
from .jobs import Queue

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.getenv("FW_OUTPUT", os.path.join(ROOT, "output"))
STATIC = {"/": "web/index.html", "/index.html": "web/index.html"}


def run(params: dict, progress) -> dict:
    """Job runner: render, then return what the UI needs."""
    from .pipeline import generate
    brand = brands.BRANDS.get(params.get("brand") or "")
    fmt = params.get("format") or (brand or {}).get("format") or "short"
    path = generate(params.get("topic") or "video", out_dir=OUT, fmt=fmt,
                    scenes=int(params.get("scenes") or 6), minutes=int(params.get("minutes") or 10),
                    use_youtube=bool(params.get("youtube")), script_file=params.get("script"),
                    brand=brand, voice_preset=params.get("voice") or (brand or {}).get("voice"),
                    progress=progress)
    base = path[:-4]
    plan = json.load(open(base + ".json", encoding="utf-8"))
    meta = json.load(open(base + ".youtube.json", encoding="utf-8")) if os.path.exists(base + ".youtube.json") else {}
    url = lambda p: "/output/" + os.path.basename(p) if os.path.exists(p) else None  # noqa: E731
    return {"video": url(path), "path": path, "title": plan.get("title"), "format": plan.get("format"),
            "thumb": url(base + ".thumb.jpg"), "cover": url(base + ".cover.jpg"), "srt": url(base + ".srt"),
            "youtube": meta, "chapters": plan.get("chapters", []),
            "scenes": [{"narration": s["narration"], "chapter": s.get("chapter")} for s in plan["scenes"]]}


def presets() -> dict:
    return {
        "voices": [{"id": k, "engine": v[0], "voice": v[1]} for k, v in voice.PRESETS.items()],
        "kokoro": voice.kokoro_available(), "default_voice": voice.DEFAULT,
        "brands": [{"id": k, "name": b["name"], "accent": b.get("accent", "#C88F3B")} for k, b in brands.BRANDS.items()],
        "formats": list(FORMATS), "clip": relevance.available(), "encoder": render.encoder(),
        "stock": {"pexels": bool(os.getenv("PEXELS_API_KEY")), "pixabay": bool(os.getenv("PIXABAY_API_KEY"))},
    }


def make_handler(queue: Queue):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, data, code: int = 200) -> None:
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, path: str) -> None:
            if not os.path.isfile(path):
                return self._json({"error": "not found"}, 404)
            size = os.path.getsize(path)
            start, end = 0, size - 1
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):  # range support so <video> can seek
                a, _, b = rng[6:].partition("-")
                start, end = int(a or 0), min(int(b), size - 1) if b else size - 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(path)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = f.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in STATIC:
                return self._file(os.path.join(ROOT, STATIC[path]))
            if path.startswith("/assets/"):
                return self._file(os.path.join(ROOT, "assets", os.path.basename(path)))
            if path == "/api/presets":
                return self._json(presets())
            if path == "/api/jobs":
                return self._json(queue.list())
            if path.startswith("/api/jobs/"):
                job = queue.get(path.rsplit("/", 1)[-1])
                return self._json(job) if job else self._json({"error": "unknown job"}, 404)
            if path.startswith("/output/"):
                return self._file(os.path.join(OUT, os.path.basename(path)))  # basename blocks traversal
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path != "/api/jobs":
                return self._json({"error": "not found"}, 404)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self._json({"error": "invalid JSON"}, 400)
            topic = str(body.get("topic", "")).strip()[:160]
            if not topic:
                return self._json({"error": "topic required"}, 400)
            params = {"topic": topic, "format": body.get("format") if body.get("format") in FORMATS else "short",
                      "scenes": max(3, min(10, int(body.get("scenes") or 6))),
                      "minutes": max(3, min(20, int(body.get("minutes") or 10))),
                      "voice": body.get("voice") if body.get("voice") in voice.PRESETS else None,
                      "brand": body.get("brand") if body.get("brand") in brands.BRANDS else None,
                      "youtube": bool(body.get("youtube"))}
            example = os.path.join(ROOT, "examples", os.path.basename(str(body.get("example") or "")))
            if body.get("example") and os.path.isfile(example):  # bundled example scripts only
                params["script"] = example
            self._json({"id": queue.submit(params)}, 201)

        def do_DELETE(self):
            if self.path.startswith("/api/jobs/"):
                return self._json({"cancelled": queue.cancel(self.path.rsplit("/", 1)[-1])})
            self._json({"error": "not found"}, 404)

        def log_message(self, *_):  # the pipeline prints its own progress
            pass

    return Handler


def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    os.makedirs(OUT, exist_ok=True)
    queue = Queue(os.path.join(OUT, "jobs.db"), run).start(1)
    print(f"Framewright on http://localhost:{port}", flush=True)
    ThreadingHTTPServer((host, port), make_handler(queue)).serve_forever()
