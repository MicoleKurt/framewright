"""Core invariants. Run: python -m pytest tests"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from framewright import factcheck, formats, render, voice  # noqa: E402
from framewright.jobs import Queue  # noqa: E402
from framewright.pipeline import chapter_list, clock  # noqa: E402


def test_xfade_offsets_keep_total_length():
    durs = [3.0, 4.5, 2.0, 5.0]
    assert render.xfade_offsets(durs) == [3.0, 7.5, 9.5]  # transition k starts where slot k ends


def test_chapters_start_at_zero_and_need_three():
    plan = {"scenes": [{"narration": "a"}, {"narration": "b", "chapter": "One"},
                       {"narration": "c", "chapter": "Two"}, {"narration": "d", "chapter": "Three"}]}
    ch = chapter_list(plan, [0, 30, 95, 160])
    assert ch[0] == (0.0, "Intro") and [c for _, c in ch] == ["Intro", "One", "Two", "Three"]
    assert chapter_list({"scenes": plan["scenes"][:2]}, [0, 30]) == []  # < 3 chapters: YouTube ignores them


def test_chapters_drop_ones_shorter_than_ten_seconds():
    plan = {"scenes": [{"narration": "a", "chapter": "A"}, {"narration": "b", "chapter": "B"},
                       {"narration": "c", "chapter": "C"}, {"narration": "d", "chapter": "D"}]}
    assert [c for _, c in chapter_list(plan, [0, 4, 40, 90])] == ["A", "C", "D"]


def test_clock_format():
    assert clock(0) == "0:00" and clock(75) == "1:15" and clock(3725) == "1:02:05"


def test_respell_maps_back_to_real_spelling():
    text, plan = voice.respell("Haise threw Philip.", {"Haise": "Hay zuh bee lus"})
    assert text == "Hay zuh bee lus threw Philip."
    words = [{"text": w, "start": i, "end": i + 1} for i, w in enumerate(text.split())]
    out = voice._remap(words, plan)
    assert [w["text"] for w in out] == ["Haise", "threw", "Philip"]
    assert out[0]["start"] == 0 and out[0]["end"] == 4


def test_factcheck_drops_invented_numbers():
    src = "Steamboat Willie premiered in New York in 1928."
    text, dropped = factcheck.clean("It premiered in 1928. It cost 4500 dollars.", src)
    assert text == "It premiered in 1928." and dropped == ["It cost 4500 dollars."]


def test_formats():
    assert formats.get("long").w == 1920 and not formats.get("long").vertical
    assert formats.get("nope").name == "short"


def test_long_captions_have_chapter_cards_but_no_burned_words():
    render.use(formats.LONG)
    try:
        path = os.path.join(tempfile.mkdtemp(), "c.ass")
        words = [{"text": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.3} for i in range(50)]
        render.captions_ass(words, path, "T", chapters=[(0, "Intro"), (5, "One"), (12, "Two")])
        body = open(path, encoding="utf-8").read()
        assert "CHAPTER 1" in body and "CHAPTER 2" in body and "Dialogue: 0," not in body
    finally:
        render.use(formats.SHORT)


def test_queue_persists_and_requeues_running_jobs():
    db = os.path.join(tempfile.mkdtemp(), "jobs.db")
    q = Queue(db, runner=None)
    jid = q.submit({"topic": "x"})
    assert q._claim()["id"] == jid and q.get(jid)["status"] == "running"
    q2 = Queue(db, runner=None)  # "restart": a running job goes back to queued
    assert q2.get(jid)["status"] == "queued"


def test_queue_runs_jobs():
    db = os.path.join(tempfile.mkdtemp(), "jobs.db")
    q = Queue(db, runner=lambda p, prog: (prog("Working", 50), {"echo": p["topic"]})[1]).start(1)
    jid = q.submit({"topic": "hello"})
    for _ in range(50):
        if q.get(jid)["status"] == "done":
            break
        time.sleep(0.1)
    assert q.get(jid)["result"] == {"echo": "hello"}


def test_join_crossfades_keep_timeline_length():
    import shutil
    if not shutil.which("ffmpeg"):
        return
    work = tempfile.mkdtemp()
    slots, o = [1.0, 1.5, 0.8, 1.2, 0.9], 0.3
    clips = []
    for i, d in enumerate(slots):
        length = d + (o if i < len(slots) - 1 else 0)
        render.ff("-f", "lavfi", "-i", f"color=c=0x{i*40:02x}2040:s=320x240:d={length:.3f}:r=30",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", f"c{i}.mp4", cwd=work)
        clips.append(f"c{i}.mp4")
    render.join(work, clips, slots, "out.mp4", overlap=o, group=2)  # forces the grouped path
    assert abs(render.duration(os.path.join(work, "out.mp4")) - sum(slots)) < 0.12


def test_script_cleanup_drops_headings_labels_repeats_and_filler():
    from framewright.script import _clean, _paragraphs
    raw = ("Oxygen Tank Exploded\nOn April 13, 1970, an explosion ripped through the service module, venting oxygen.\n\n"
           "The promise: you will learn how three men got home in a crippled spacecraft.\n\n"
           "The crew prepared for the long journey home. Mission Control worked through the night on it.")
    paras = _paragraphs(raw)
    assert paras[0].startswith("On April 13") and paras[1].startswith("you will learn")
    seen = set()
    first = _clean(paras, "April 13, 1970", [], seen)
    assert "journey" not in " ".join(first)
    again = _clean(["On April 13, 1970, an explosion ripped through the service module, venting oxygen. "
                    "Engineers built an adapter from plastic and tape that night."], "April 13, 1970", [], seen)
    assert again == ["Engineers built an adapter from plastic and tape that night."]
