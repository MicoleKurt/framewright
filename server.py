"""Shortcut: python server.py -> http://localhost:8000  (same as `iframesco serve`)"""
import os

from iframesco.server import serve

if __name__ == "__main__":
    serve(int(os.getenv("PORT", 8000)))
