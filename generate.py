"""CLI: python generate.py "the history of coffee" [--scenes 6]"""
import argparse

from videogen.brands import BRANDS
from videogen.pipeline import generate

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Topic in, vertical mp4 out.")
    p.add_argument("topic")
    p.add_argument("--scenes", type=int, default=6)
    p.add_argument("--youtube", action="store_true",
                   help="add real Creative Commons footage from YouTube via yt-dlp (slower)")
    p.add_argument("--script", help="JSON script to use instead of the LLM (see scripts/)")
    p.add_argument("--brand", choices=sorted(BRANDS), help="channel preset for title/end card + thumbnail")
    a = p.parse_args()
    print(generate(a.topic, scenes=a.scenes, use_youtube=a.youtube, script_file=a.script,
                   brand=BRANDS.get(a.brand)))
