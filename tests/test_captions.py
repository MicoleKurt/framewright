"""Caption timing invariants. Run: python -m pytest tests  (or python tests/test_captions.py)"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from videogen import render  # noqa: E402


def _secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _events(words: list[dict]) -> list[tuple[float, float]]:
    path = os.path.join(tempfile.mkdtemp(), "t.ass")
    render.captions_ass(words, path, title="Test")
    with open(path, encoding="utf-8") as f:
        return [(_secs(l.split(",")[1]), _secs(l.split(",")[2])) for l in f if l.startswith("Dialogue: 0")]


def _words(n: int = 200, seed: int = 1) -> list[dict]:
    rnd, t, out = random.Random(seed), 0.0, []
    for i in range(n):
        d = rnd.uniform(0.15, 0.5)
        out.append({"text": f"w{i}", "start": t, "end": t + d})
        t += d + rnd.choice([0.02, 0.05, 0.1, 0.3])
    return out


def test_one_event_per_word():
    assert len(_events(_words())) == 200


def test_caption_events_never_overlap():
    ev = _events(_words())
    assert all(b[0] >= a[1] - 0.01 for a, b in zip(ev, ev[1:]))  # 10ms = ASS centisecond rounding


def test_phrases_break_on_pauses():
    words = [{"text": "a", "start": 0, "end": 0.3}, {"text": "b", "start": 0.9, "end": 1.2}]
    assert len(render._phrases(words, 4)) == 2


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
