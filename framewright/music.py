"""Background music matched to the script's mood, from a local library you are licensed to use.

Drop tracks in `music/` and describe them in `music/library.json`:

    [{"file": "dark-ambient.mp3", "moods": ["mysterious", "tense"],
      "license": "Pixabay Content License", "credit": ""}]

Good free sources: YouTube Audio Library (Studio > Audio library), Pixabay Music, and
incompetech.com (CC BY 4.0, needs the credit line, which is added to the description).
No match -> the generated ambient pad in render.music().
"""
import json
import os
import random

MOODS = ["mysterious", "tense", "somber", "calm", "uplifting", "triumphant", "epic"]
LIB_DIR = os.getenv("FW_MUSIC_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "music"))


def library() -> list[dict]:
    path = os.path.join(LIB_DIR, "library.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        tracks = json.load(f)
    return [t for t in tracks if os.path.exists(os.path.join(LIB_DIR, t["file"]))]


def pick(mood: str, seed: str = "") -> dict | None:
    """A track tagged with `mood` (or a neighbouring mood); stable per video via `seed`."""
    tracks = library()
    neighbours = {"mysterious": ["tense", "somber"], "tense": ["mysterious", "epic"], "somber": ["calm", "mysterious"],
                  "calm": ["somber", "uplifting"], "uplifting": ["triumphant", "calm"],
                  "triumphant": ["epic", "uplifting"], "epic": ["triumphant", "tense"]}
    for m in [mood, *neighbours.get(mood, [])]:
        matches = [t for t in tracks if m in t.get("moods", [])]
        if matches:
            t = random.Random(seed).choice(matches)
            return {**t, "path": os.path.join(LIB_DIR, t["file"])}
    return None
