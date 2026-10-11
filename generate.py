"""Shortcut: python generate.py "topic" [--format long] ...  (same as `framewright make`)"""
import sys

from framewright.__main__ import main

if __name__ == "__main__":
    main(["make", *sys.argv[1:]])
