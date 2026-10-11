"""Persistent job queue on SQLite: renders survive restarts and run in N worker threads.

No Redis/Postgres needed for a single machine. A job that was running when the server died is
re-queued on startup. Scale out by starting more worker *processes* against the same database
(`python -m iframesco worker`): claims are atomic, and each process renders one job at a time
(the renderer keeps per-process format state, so threads would collide).
"""
import json
import os
import sqlite3
import threading
import time
import traceback
import uuid
from typing import Callable

SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, params TEXT NOT NULL, status TEXT NOT NULL, pct REAL DEFAULT 0, msg TEXT DEFAULT '',
  log TEXT DEFAULT '[]', result TEXT, error TEXT, created REAL, updated REAL)"""


class Queue:
    def __init__(self, path: str, runner: Callable[[dict, Callable[[str, float], None]], dict],
                 requeue: bool = True):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path, self.runner = path, runner
        self.lock = threading.Lock()
        with self._db() as db:
            db.execute(SCHEMA)
            if requeue:
                db.execute("UPDATE jobs SET status='queued', msg='Re-queued after restart' WHERE status='running'")
        self.wake = threading.Event()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    # -------------------------------------------------------- API
    def submit(self, params: dict) -> str:
        job_id = uuid.uuid4().hex[:10]
        now = time.time()
        with self.lock, self._db() as db:
            db.execute("INSERT INTO jobs (id, params, status, msg, created, updated) VALUES (?,?,?,?,?,?)",
                       (job_id, json.dumps(params), "queued", "Queued", now, now))
        self.wake.set()
        return job_id

    def get(self, job_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._row(row) if row else None

    def list(self, limit: int = 30) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(r, brief=True) for r in rows]

    def cancel(self, job_id: str) -> bool:
        with self.lock, self._db() as db:
            return db.execute("UPDATE jobs SET status='cancelled', msg='Cancelled' WHERE id=? AND status='queued'",
                              (job_id,)).rowcount > 0

    @staticmethod
    def _row(r: sqlite3.Row, brief: bool = False) -> dict:
        d = dict(r)
        d["params"] = json.loads(d["params"])
        d["result"] = json.loads(d["result"]) if d["result"] else None
        d["log"] = [] if brief else json.loads(d["log"] or "[]")
        if brief and d["result"]:
            d["result"] = {k: d["result"].get(k) for k in ("video", "title", "thumb", "format")}
        return d

    # -------------------------------------------------------- workers
    def _claim(self) -> dict | None:
        with self.lock, self._db() as db:
            for row in db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 5").fetchall():
                # atomic across processes: only one worker flips queued -> running
                if db.execute("UPDATE jobs SET status='running', updated=? WHERE id=? AND status='queued'",
                              (time.time(), row["id"])).rowcount:
                    return self._row(row)
        return None

    def _update(self, job_id: str, **fields) -> None:
        fields["updated"] = time.time()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.lock, self._db() as db:
            db.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), job_id))

    def _work(self) -> None:
        while True:
            job = self._claim()
            if not job:
                self.wake.wait(2)
                self.wake.clear()
                continue
            log: list[str] = []

            def progress(msg: str, pct: float, job_id=job["id"]) -> None:
                if not log or log[-1] != msg:
                    log.append(msg)
                self._update(job_id, msg=msg, pct=pct, log=json.dumps(log[-200:]))

            try:
                result = self.runner(job["params"], progress)
                self._update(job["id"], status="done", pct=100, msg="Done", result=json.dumps(result))
            except Exception as e:
                traceback.print_exc()
                self._update(job["id"], status="error", msg=str(e)[:300], error=traceback.format_exc()[-4000:])

    def start(self, workers: int = 1) -> "Queue":
        for _ in range(workers):
            threading.Thread(target=self._work, daemon=True).start()
        return self

    def run_forever(self) -> None:
        """Standalone worker process."""
        self._work()
