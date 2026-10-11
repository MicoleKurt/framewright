"""Real footage from YouTube via yt-dlp, restricted to Creative Commons (CC BY) videos.

Only videos whose metadata licence is Creative Commons are used, and every clip's
title/channel/URL is returned so the video can carry attribution (required by CC BY).
Only a short segment is downloaded, never the whole video.
"""
import glob
import re
import urllib.parse

import yt_dlp
from yt_dlp.utils import download_range_func

CC_FILTER = "EgIwAQ%253D%253D"  # YouTube search filter: Creative Commons only
# music mixes / lyric videos are a static card with burned-in text, not usable b-roll
NOT_FOOTAGE = re.compile(r"\b(music|mix|playlist|lofi|lo-fi|lyrics?|podcast|beats?|ambience)\b", re.I)
QUIET = {"quiet": True, "no_warnings": True, "noprogress": True}


def search_cc(query: str, limit: int = 6) -> list[dict]:
    """Creative Commons search results (flat: id, title, duration), shortest-useful first."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}&sp={CC_FILTER}"
    with yt_dlp.YoutubeDL({**QUIET, "extract_flat": True, "playlistend": limit * 2}) as ydl:
        entries = ydl.extract_info(url, download=False).get("entries") or []
    # skip shorts-length teasers and hour-long streams: 15s-20min is usually real b-roll
    usable = [e for e in entries if e.get("id") and 15 <= (e.get("duration") or 0) <= 1200
              and not NOT_FOOTAGE.search(e.get("title") or "")]
    return usable[:limit]


def cc_clip(query: str, path_stem: str, seconds: float = 8.0, used: set | None = None,
            orientation: str = "portrait") -> dict | None:
    """Download a `seconds`-long 1080p segment from the first verified-CC result.
    Returns {"path", "title", "channel", "url", "license"} or None."""
    used = used if used is not None else set()
    for entry in search_cc(query):
        url = f"https://www.youtube.com/watch?v={entry['id']}"
        if url in used:
            continue
        used.add(url)
        try:
            with yt_dlp.YoutubeDL(QUIET) as ydl:
                info = ydl.extract_info(url, download=False)
            licence = info.get("license") or ""
            if "creative commons" not in licence.lower():  # trust the video page, not the search filter
                continue
            dur = info.get("duration") or 0
            start = min(max(3.0, dur * 0.25), max(0.0, dur - seconds - 1))  # skip intros/title cards
            opts = {**QUIET,
                    "format": "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]",
                    "download_ranges": download_range_func(None, [(start, start + seconds)]),
                    "force_keyframes_at_cuts": True,
                    "outtmpl": f"{path_stem}.%(ext)s"}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            files = glob.glob(f"{glob.escape(path_stem)}.*")
            if not files:
                continue
            path = files[0]
            return {"path": path, "title": info.get("title"), "channel": info.get("uploader"),
                    "url": url, "license": licence}
        except Exception as e:
            print(f"[youtube] skip {url}: {e}")
    return None
