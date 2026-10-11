"""Shortcut: python generate.py "topic" [--format long] ...  (same as `iframesco make`)"""
import sys

from iframesco.__main__ import main

if __name__ == "__main__":
    main(["make", *sys.argv[1:]])
