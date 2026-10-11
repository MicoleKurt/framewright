"""Shortcut: python server.py -> http://localhost:8000  (same as `framewright serve`)"""
import os

from framewright.server import serve

if __name__ == "__main__":
    serve(int(os.getenv("PORT", 8000)))
