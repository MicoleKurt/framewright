"""Framewright CLI.

  framewright make "The Apollo 13 rescue" --format long --minutes 10
  framewright make "Alexander" --script examples/alexander.json
  framewright serve                       # web UI + queue
  framewright worker                      # extra render process for the same queue
  framewright voices --sample "Some text" # render one sample per voice preset
  framewright youtube auth|channel|videos|update|schedule|thumbnail|playlist|captions|upload|analytics
"""
import argparse
import json
import os
import sys


def _make(a) -> None:
    from .brands import BRANDS
    from .pipeline import generate
    brand = BRANDS.get(a.brand) if a.brand else None
    fmt = a.format or (brand or {}).get("format") or "short"
    print(generate(a.topic, out_dir=a.out, fmt=fmt, scenes=a.scenes, minutes=a.minutes, use_youtube=a.youtube_cc,
                   script_file=a.script, brand=brand, voice_preset=a.voice or (brand or {}).get("voice")))


def _voices(a) -> None:
    from . import voice
    os.makedirs(a.out, exist_ok=True)
    for name in voice.PRESETS:
        path, _ = voice.synthesize(a.sample, os.path.join(a.out, f"voice-{name}"), preset=name)
        print(f"{name:12s} {voice.resolve(name)[:2]} -> {path}")


def _youtube(a) -> None:
    from . import youtube_api as yt
    cmd, x = a.cmd, a.args
    calls = {
        "auth": lambda: yt.auth(),
        "channel": lambda: yt.channel(),
        "videos": lambda: yt.list_videos(int(x[0]) if x else 25),
        "video": lambda: yt.get_video(x[0]),
        "update": lambda: yt.update_video(x[0], **json.loads(x[1])),       # update ID '{"title": "..."}'
        "schedule": lambda: yt.schedule(x[0], x[1]),                        # schedule ID 2026-10-12T19:00:00-04:00
        "visibility": lambda: yt.set_visibility(x[0], x[1]),
        "thumbnail": lambda: yt.set_thumbnail(x[0], x[1]),
        "playlist": lambda: yt.add_to_playlist(x[0], x[1]),
        "captions": lambda: yt.upload_captions(x[0], x[1]),
        "analytics": lambda: yt.analytics(x[0] if x else None),
        "upload": lambda: _upload(yt, x),
    }
    if cmd not in calls:
        sys.exit(f"unknown youtube command {cmd}; one of {', '.join(calls)}")
    try:
        print(json.dumps(calls[cmd](), indent=2, default=str))
    except yt.NotAuthorized as e:
        sys.exit(str(e))


def _upload(yt, x):
    from .mcp_server import upload_render
    return upload_render(x[0], publish_at=x[1] if len(x) > 1 else "")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="framewright", description="Open-source video generator for Shorts and long-form.")
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("make", help="render a video")
    m.add_argument("topic")
    m.add_argument("--format", choices=["short", "long"])
    m.add_argument("--scenes", type=int, default=6, help="Shorts: number of paragraphs")
    m.add_argument("--minutes", type=int, default=10, help="long-form: target length")
    m.add_argument("--script", help="hand-written script JSON instead of the LLM")
    m.add_argument("--voice", help="voice preset (framewright voices)")
    m.add_argument("--brand", help="brand preset from brands.py / local/brands.local.json")
    m.add_argument("--youtube-cc", action="store_true", help="add Creative Commons YouTube clips (slower)")
    m.add_argument("--out", default="output")
    m.set_defaults(fn=_make)

    s = sub.add_parser("serve", help="web UI + job queue")
    s.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    s.set_defaults(fn=lambda a: __import__("framewright.server", fromlist=["serve"]).serve(a.port))

    w = sub.add_parser("worker", help="extra render worker for the shared queue")
    w.set_defaults(fn=lambda a: _worker())

    v = sub.add_parser("voices", help="render a sample per voice preset")
    v.add_argument("--sample", default="Everyone knows how the story ends. Almost nobody knows how it started.")
    v.add_argument("--out", default="samples")
    v.set_defaults(fn=_voices)

    y = sub.add_parser("youtube", help="manage your channel via the YouTube Data API")
    y.add_argument("cmd")
    y.add_argument("args", nargs="*")
    y.set_defaults(fn=_youtube)

    a = p.parse_args(argv)
    a.fn(a)


def _worker() -> None:
    from .jobs import Queue
    from .server import OUT, run
    Queue(os.path.join(OUT, "jobs.db"), run, requeue=False).run_forever()


if __name__ == "__main__":
    main()
