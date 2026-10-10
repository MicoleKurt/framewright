"""Topic research + stock media lookup. Keyless: Wikipedia / Wikimedia Commons, optional Pexels."""
import os
import time
import requests

# Wikimedia throttles anonymous-looking clients; their policy asks for a descriptive UA with contact info.
UA = {"User-Agent": os.getenv("WIKI_USER_AGENT", "videogen-prototype/0.1 (topic-to-video research)")}
WIKI = "https://en.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"


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


def wiki_facts(topic: str) -> dict:
    """Best-matching Wikipedia article: title + plain-text intro."""
    r = _api(WIKI, {
        "action": "query", "generator": "search", "gsrsearch": topic,
        "gsrlimit": 1, "prop": "extracts", "explaintext": 1, "exintro": 1,
    })
    pages = list(r.get("query", {}).get("pages", {}).values())
    if not pages:
        return {"title": topic, "text": ""}
    return {"title": pages[0]["title"], "text": pages[0].get("extract", "")}


def commons_images(query: str, limit: int = 6) -> list[str]:
    """Large photo URLs from Wikimedia Commons matching the query."""
    r = _api(COMMONS, {
        "action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6, "gsrlimit": limit * 2, "prop": "imageinfo", "iiprop": "url|size|mime",
        "iiurlwidth": 1280,  # standard thumb size: cached, not rate-limited like odd widths
    })
    out = []
    for p in sorted(r.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") in ("image/jpeg", "image/png") and info.get("width", 0) >= 800:
            out.append(info.get("thumburl") or info["url"])
    return out[:limit]


def pexels_videos(query: str, limit: int = 3) -> list[str]:
    """Real stock footage when PEXELS_API_KEY is set (free key). Returns mp4 URLs."""
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return []
    r = requests.get("https://api.pexels.com/videos/search", timeout=20,
                     headers={"Authorization": key},
                     params={"query": query, "per_page": limit, "orientation": "portrait"}).json()
    urls = []
    for v in r.get("videos", []):
        files = sorted((f for f in v["video_files"] if f.get("height", 0) >= 1280),
                       key=lambda f: f["height"])
        if files:
            urls.append(files[0]["link"])
    return urls


def download(url: str, path: str, retries: int = 4) -> str:
    for attempt in range(retries):
        with requests.get(url, headers=UA, timeout=60, stream=True) as r:
            if r.status_code == 429 and attempt < retries - 1:
                wait = r.headers.get("Retry-After", "")
                time.sleep(float(wait) if wait.isdigit() else 3 * 2 ** attempt)
                continue
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
            return path
    return path
