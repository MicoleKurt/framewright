"""CLI: python generate.py "the history of coffee" [--scenes 6]"""
import argparse

from videogen.pipeline import generate

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Topic in, vertical mp4 out.")
    p.add_argument("topic")
    p.add_argument("--scenes", type=int, default=6)
    a = p.parse_args()
    print(generate(a.topic, scenes=a.scenes))
