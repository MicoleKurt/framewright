"""Tiny web UI (stdlib only): python server.py -> http://localhost:8000"""
import json
import mimetypes
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from videogen.pipeline import generate

ROOT = os.path.dirname(os.path.abspath(__file__))
JOBS: dict[str, dict] = {}
RENDER_LOCK = threading.Lock()  # one render at a time: ffmpeg + CPU LLM saturate the machine


def run_job(job_id: str, topic: str, scenes: int, use_youtube: bool) -> None:
    job = JOBS[job_id]

    def progress(msg: str, pct: float) -> None:
        job.update(msg=msg, pct=pct, log=job["log"] + [msg])

    try:
        with RENDER_LOCK:
            job["status"] = "running"
            path = generate(topic, out_dir=os.path.join(ROOT, "output"), scenes=scenes,
                            use_youtube=use_youtube, progress=progress)
        job.update(status="done", video="/output/" + os.path.basename(path),
                   script=json.load(open(path[:-4] + ".json")))
    except Exception as e:
        job.update(status="error", msg=str(e)[:300])


class Handler(BaseHTTPRequestHandler):
    def _json(self, data: dict, code: int = 200) -> None:
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
            start, end = int(a or 0), int(b) if b else size - 1
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
            self.wfile.write(f.read(end - start + 1))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._file(os.path.join(ROOT, "web", "index.html"))
        if self.path.startswith("/api/jobs/"):
            job = JOBS.get(self.path.rsplit("/", 1)[-1])
            return self._json(job) if job else self._json({"error": "unknown job"}, 404)
        if self.path.startswith("/output/"):
            name = os.path.basename(self.path)  # basename blocks path traversal
            return self._file(os.path.join(ROOT, "output", name))
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/jobs":
            return self._json({"error": "not found"}, 404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        topic = str(body.get("topic", "")).strip()[:120]
        if not topic:
            return self._json({"error": "topic required"}, 400)
        scenes = max(3, min(10, int(body.get("scenes", 6))))
        job_id = uuid.uuid4().hex[:10]
        JOBS[job_id] = {"id": job_id, "topic": topic, "status": "queued", "pct": 0, "msg": "Queued", "log": []}
        threading.Thread(target=run_job, args=(job_id, topic, scenes, bool(body.get("youtube"))),
                         daemon=True).start()
        self._json({"id": job_id}, 201)

    def log_message(self, *_):  # keep the console quiet; pipeline prints its own progress
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"videogen UI on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
