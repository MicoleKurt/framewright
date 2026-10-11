"""MCP server: your YouTube channel + Framewright renders as tools for Claude (or any MCP client).

    claude mcp add youtube -- python -m framewright.mcp_server       # Claude Code
    framewright-mcp                                                   # after `pip install -e .`

Read tools are safe to auto-approve; write tools (update/schedule/upload/visibility) change your
channel, so leave them on "ask" in your client's permission settings.
"""
import json
import os

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from . import youtube_api as api
from .jobs import Queue

mcp = _Server("framewright-youtube")
DB = os.getenv("FW_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "jobs.db"))


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except api.NotAuthorized as e:
        return {"error": str(e)}
    except Exception as e:  # surface API errors as data the model can act on
        return {"error": f"{type(e).__name__}: {str(e)[:400]}"}


# ---------------------------------------------------------------- read
@mcp.tool()
def channel_overview() -> dict:
    """Channel title, handle, subscribers, total views and video count."""
    return _safe(api.channel)


@mcp.tool()
def list_videos(limit: int = 25) -> list | dict:
    """Recent uploads incl. private/scheduled: id, title, privacy, publish_at, views, url."""
    return _safe(api.list_videos, limit)


@mcp.tool()
def get_video(video_id: str) -> dict:
    """Full metadata for one video: title, description, tags, privacy, schedule, stats."""
    return _safe(api.get_video, video_id)


@mcp.tool()
def list_playlists() -> list | dict:
    """The channel's playlists with item counts."""
    return _safe(api.list_playlists)


@mcp.tool()
def video_analytics(video_id: str = "", days: int = 28, top: int = 10) -> list | dict:
    """Views, watch minutes, average view duration and average % viewed (retention) for the last
    `days`; one video if `video_id` is given, else the top videos by views."""
    return _safe(api.analytics, video_id or None, days, top)


# ---------------------------------------------------------------- write
@mcp.tool()
def update_video(video_id: str, title: str = "", description: str = "", tags: list[str] | None = None) -> dict:
    """Change title / description / tags. Empty values are left unchanged."""
    return _safe(api.update_video, video_id, title or None, description or None, tags)


@mcp.tool()
def schedule_video(video_id: str, publish_at: str) -> dict:
    """Schedule a video to go public at an ISO time with offset, e.g. 2026-10-12T19:00:00-04:00."""
    return _safe(api.schedule, video_id, publish_at)


@mcp.tool()
def set_visibility(video_id: str, privacy: str) -> dict:
    """Set privacy to private, unlisted or public (public publishes immediately)."""
    return _safe(api.set_visibility, video_id, privacy)


@mcp.tool()
def set_audience(video_id: str, made_for_kids: bool = False, synthetic_media: bool = False) -> dict:
    """Set the made-for-kids flag and the altered/synthetic content disclosure."""
    return _safe(api.set_audience, video_id, made_for_kids, synthetic_media)


@mcp.tool()
def set_thumbnail(video_id: str, image_path: str) -> dict:
    """Upload a custom thumbnail (JPG/PNG, < 2 MB; Shorts need 9:16). Needs a phone-verified channel."""
    return _safe(api.set_thumbnail, video_id, image_path)


@mcp.tool()
def add_to_playlist(video_id: str, playlist: str) -> dict:
    """Add a video to a playlist by id or title (a missing title is created as a public playlist)."""
    return _safe(api.add_to_playlist, video_id, playlist)


@mcp.tool()
def upload_captions(video_id: str, srt_path: str, language: str = "en") -> dict:
    """Attach an .srt caption track (Framewright writes one next to every render)."""
    return _safe(api.upload_captions, video_id, srt_path, language)


@mcp.tool()
def upload_render(mp4_path: str, publish_at: str = "", privacy: str = "private", playlist: str = "") -> dict:
    """Upload a Framewright render using its sidecar files (.youtube.json metadata, thumbnail, .srt).
    With `publish_at` it is scheduled. Note: unaudited API projects keep uploads private."""
    base = mp4_path[:-4]
    meta = json.load(open(base + ".youtube.json", encoding="utf-8")) if os.path.exists(base + ".youtube.json") else {}
    # Shorts only accept 9:16 thumbnails, and only Shorts get a .cover.jpg
    thumb = next((p for p in (base + ".cover.jpg", base + ".thumb.jpg") if os.path.exists(p)), None)
    return _safe(api.upload, mp4_path, meta.get("title", os.path.basename(base)), meta.get("description", ""),
                 meta.get("tags"), privacy, publish_at or None, thumbnail=thumb, playlist=playlist or None,
                 captions=base + ".srt" if os.path.exists(base + ".srt") else None)


# ---------------------------------------------------------------- renders
@mcp.tool()
def create_video(topic: str, format: str = "long", minutes: int = 10, voice: str = "soothing",
                 brand: str = "", script_path: str = "") -> dict:
    """Queue a Framewright render (needs `framewright serve` or `framewright worker` running).
    format: short | long. Returns a job id; poll with job_status."""
    q = Queue(DB, runner=None, requeue=False)
    job = q.submit({"topic": topic, "format": format, "minutes": minutes, "voice": voice,
                    "brand": brand or None, "script": script_path or None})
    return {"job": job, "status": "queued"}


@mcp.tool()
def job_status(job_id: str) -> dict:
    """Progress of a queued render; when done, `result.video` is the mp4 path."""
    return Queue(DB, runner=None, requeue=False).get(job_id) or {"error": "unknown job"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
