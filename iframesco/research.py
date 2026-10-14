"""Topic research + media candidates. Keyless by default (Wikipedia / Wikimedia Commons);
Pexels and Pixabay stock video switch on with free API keys (PEXELS_API_KEY, PIXABAY_API_KEY).

Every candidate is a dict: url (full size), preview (small, for relevance scoring), kind
("image"|"video"), source, credit, license.
"""
import hashlib
import os
import random
import re
import shutil
import time

import requests

# Wikimedia throttles anonymous-looking clients; their policy asks for a descriptive UA.
UA = {"User-Agent": os.getenv("WIKI_USER_AGENT", "iframesco/1.0 (open-source video generator)")}
WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
CACHE = os.getenv("FS_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "iframesco", "media"))


def _api(url: str, params: dict, retries: int = 3) -> dict:
    """GET a MediaWiki API endpoint, retrying transient errors / non-JSON (maintenance pages, 429)."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=20, params={"format": "json", **params})
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Wikimedia API failed: {e}") from e
            time.sleep(2 * 2 ** attempt)
    return {}


def wiki_facts(topic: str, full: bool = False, max_chars: int = 40000) -> dict:
    """Best-matching Wikipedia article: title + plain text (intro only, or the whole article)."""
    params = {"action": "query", "generator": "search", "gsrsearch": topic, "gsrlimit": 1,
              "prop": "extracts|info", "explaintext": 1, "inprop": "url"}
    if not full:
        params["exintro"] = 1
    pages = list(_api(WIKI, params).get("query", {}).get("pages", {}).values())
    if not pages:
        return {"title": topic, "text": "", "url": ""}
    text = pages[0].get("extract", "")
    # drop reference-ish tail sections that only add noise for the writer
    text = re.split(r"\n==+ (See also|References|Notes|Further reading|External links|Bibliography) ==+", text)[0]
    return {"title": pages[0]["title"], "text": text[:max_chars], "url": pages[0].get("fullurl", "")}


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


HD_WIDTH = int(os.getenv("FS_IMG_WIDTH", "1920"))  # photos are fetched at HD so 1080p/vertical crops stay sharp
MIN_WIDTH = int(os.getenv("FS_MIN_IMG_WIDTH", "1400"))


def commons_images(query: str, limit: int = 8) -> list[dict]:
    """Photos from Wikimedia Commons matching the query, with licence + author for credits."""
    r = _api(COMMONS, {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": limit * 2, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist",
        "iiurlwidth": HD_WIDTH,  # standard thumb step (1280/1600/1920): cached, not rate-limited like odd widths
    })
    out = []
    for p in sorted(r.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png") or info.get("width", 0) < 800:
            continue
        full = info.get("thumburl") or info["url"]
        meta = info.get("extmetadata", {})
        out.append({
            "url": full, "preview": re.sub(r"/\d+px-", "/330px-", full), "kind": "image",
            "source": "Wikimedia Commons", "title": p.get("title", "").removeprefix("File:"),
            "credit": _strip_html(meta.get("Artist", {}).get("value", "")),
            "license": meta.get("LicenseShortName", {}).get("value", ""),
            "page": info.get("descriptionurl", ""), "width": info.get("width", 0),
        })
    hd = [c for c in out if c["width"] >= MIN_WIDTH]  # prefer HD, but a sharp small portrait beats no portrait
    return (hd + [c for c in out if c["width"] < MIN_WIDTH])[:limit]


SKIP_FILE = ("logo", "icon", "flag of", "signature", "symbol", "wordmark", "seal of", "stub", "question book",
             "padlock", "commons-", "wiktionary", "edit-clear", "disambig", "ambox", "crystal ")


def wiki_images(article: str, limit: int = 12) -> list[dict]:
    """Photos used in a Wikipedia article. Editors already picked them for that article, so they are
    about the subject (unlike a free-text Commons search). Logos, flags and UI icons are skipped."""
    r = _api(WIKI, {
        "action": "query", "titles": article, "redirects": 1, "generator": "images", "gimlimit": 60,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription", "iiurlwidth": HD_WIDTH,
    })
    out = []
    for p in r.get("query", {}).get("pages", {}).values():
        title = p.get("title", "").removeprefix("File:")
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in ("image/jpeg", "image/png") or info.get("width", 0) < 500:
            continue
        if any(w in title.lower() for w in SKIP_FILE):
            continue
        full = info.get("thumburl") or info["url"]
        meta = info.get("extmetadata", {})
        out.append({
            "url": full, "preview": re.sub(r"/\d+px-", "/330px-", full), "kind": "image",
            "source": "Wikimedia Commons", "title": title, "article": article,
            "description": _strip_html(meta.get("ImageDescription", {}).get("value", ""))[:300],
            "credit": _strip_html(meta.get("Artist", {}).get("value", "")),
            "license": meta.get("LicenseShortName", {}).get("value", ""),
            "page": info.get("descriptionurl", ""), "width": info.get("width", 0),
        })
    return out[:limit]


def file_image(title: str) -> list[dict]:
    """One exact Wikimedia Commons file (e.g. picked from an article), as a candidate list of 0 or 1."""
    name = title if title.startswith("File:") else f"File:{title}"
    r = _api(COMMONS, {"action": "query", "titles": name, "prop": "imageinfo",
                       "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist",
                       "iiurlwidth": HD_WIDTH})
    for p in r.get("query", {}).get("pages", {}).values():
        info = (p.get("imageinfo") or [{}])[0]
        if not info.get("url"):
            return []
        full = info.get("thumburl") or info["url"]
        meta = info.get("extmetadata", {})
        return [{"url": full, "preview": re.sub(r"/\d+px-", "/330px-", full), "kind": "image",
                 "source": "Wikimedia Commons", "title": name.removeprefix("File:"),
                 "credit": _strip_html(meta.get("Artist", {}).get("value", "")),
                 "license": meta.get("LicenseShortName", {}).get("value", ""),
                 "page": info.get("descriptionurl", ""), "width": info.get("width", 0)}]
    return []


def pexels_videos(query: str, limit: int = 3, orientation: str = "portrait") -> list[dict]:
    """Stock footage from Pexels (free key). Pexels licence: free to use, no attribution required."""
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://api.pexels.com/videos/search", timeout=20, headers={"Authorization": key},
                         params={"query": query, "per_page": limit, "orientation": orientation}).json()
    except (requests.RequestException, ValueError):
        return []
    out = []
    min_side = 1080
    for v in r.get("videos", []):
        files = sorted((f for f in v["video_files"] if min(f.get("width") or 0, f.get("height") or 0) >= min_side),
                       key=lambda f: f.get("height") or 0)
        if files:
            out.append({"url": files[0]["link"], "preview": v.get("image", ""), "kind": "video",
                        "source": "Pexels", "credit": (v.get("user") or {}).get("name", ""),
                        "license": "Pexels License", "page": v.get("url", "")})
    return out


def pixabay_videos(query: str, limit: int = 3, orientation: str = "portrait") -> list[dict]:
    """Stock footage from Pixabay (free key). Pixabay Content License: no attribution required."""
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://pixabay.com/api/videos/", timeout=20,
                         params={"key": key, "q": query[:100], "per_page": max(3, limit * 2), "safesearch": "true"}).json()
    except (requests.RequestException, ValueError):
        return []
    out = []
    for h in r.get("hits", []):
        v = (h.get("videos") or {}).get("large") or (h.get("videos") or {}).get("medium") or {}
        w, hgt = v.get("width") or 0, v.get("height") or 0
        if not v.get("url") or min(w, hgt) < 720 or ((hgt > w) != (orientation == "portrait")):
            continue
        out.append({"url": v["url"], "preview": v.get("thumbnail", ""), "kind": "video",
                    "source": "Pixabay", "credit": h.get("user", ""), "license": "Pixabay Content License",
                    "page": h.get("pageURL", "")})
    return out[:limit]


def stock_videos(query: str, limit: int = 3, orientation: str = "portrait") -> list[dict]:
    return pexels_videos(query, limit, orientation) + pixabay_videos(query, limit, orientation)


def download(url: str, path: str, retries: int = 4) -> str:
    """Download with an on-disk cache (re-renders don't re-hit Wikimedia) and 429 backoff."""
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest()[:20] + os.path.splitext(path)[1])
    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        shutil.copyfile(cached, path)
        return path
    if "wikimedia.org" in url:
        time.sleep(0.4 + random.random() * 0.4)  # be polite: serial, spaced requests
    for attempt in range(retries):
        with requests.get(url, headers=UA, timeout=60, stream=True) as r:
            if r.status_code == 429 and attempt < retries - 1:
                wait = r.headers.get("Retry-After", "")
                time.sleep(float(wait) if wait.isdigit() else 4 * 2 ** attempt)
                continue
            r.raise_for_status()
            with open(cached + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            os.replace(cached + ".part", cached)
            shutil.copyfile(cached, path)
            return path
    raise RuntimeError(f"download failed: {url}")


def fetch_bytes(url: str, timeout: int = 20) -> bytes | None:
    """Small preview fetch for relevance scoring (cached like full downloads)."""
    if not url:
        return None
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, "pv-" + hashlib.sha1(url.encode()).hexdigest()[:20])
    if os.path.exists(cached):
        with open(cached, "rb") as f:
            return f.read()
    try:
        if "wikimedia.org" in url:
            time.sleep(0.25)
        r = requests.get(url, headers=UA, timeout=timeout)
        if r.status_code != 200:
            return None
        with open(cached, "wb") as f:
            f.write(r.content)
        return r.content
    except requests.RequestException:
        return None
