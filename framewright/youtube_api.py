"""YouTube Data API v3 + Analytics client for your own channel (OAuth, free quota).

One-time setup (docs/YOUTUBE_CONNECTOR.md): create an OAuth client of type *Desktop app* in Google
Cloud, save it as ~/.framewright/client_secret.json, then `framewright youtube auth`.

Heads-up: uploads (`videos.insert`) from an unverified Cloud project are locked to *private* by
YouTube until the project passes Google's audit. Metadata, thumbnails, playlists, captions and
scheduling on existing videos are not affected.
"""
import datetime as dt
import os

HOME = os.getenv("FW_HOME", os.path.join(os.path.expanduser("~"), ".framewright"))
CLIENT_SECRET = os.getenv("FW_YT_CLIENT_SECRET", os.path.join(HOME, "client_secret.json"))
TOKEN = os.path.join(HOME, "youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl",
          "https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
UNVERIFIED_UPLOAD_NOTE = ("If this Cloud project hasn't passed YouTube's API audit, YouTube keeps API uploads "
                          "private; publish it from Studio or use set_visibility after the audit.")


class NotAuthorized(RuntimeError):
    pass


def _creds(interactive: bool = False):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if os.path.exists(TOKEN) else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save(creds)
    if creds and creds.valid:
        return creds
    if not interactive:
        raise NotAuthorized("YouTube not connected. Run: framewright youtube auth")
    if not os.path.exists(CLIENT_SECRET):
        raise NotAuthorized(f"Missing OAuth client file: {CLIENT_SECRET} (see docs/YOUTUBE_CONNECTOR.md)")
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES).run_local_server(port=0)
    _save(creds)
    return creds


def _save(creds) -> None:
    os.makedirs(HOME, exist_ok=True)
    with open(TOKEN, "w") as f:
        f.write(creds.to_json())


def auth() -> dict:
    _creds(interactive=True)
    return channel()


def yt():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def yta():
    from googleapiclient.discovery import build
    return build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)


# ---------------------------------------------------------------- read

def channel() -> dict:
    r = yt().channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    c = r["items"][0]
    return {"id": c["id"], "title": c["snippet"]["title"], "handle": c["snippet"].get("customUrl"),
            "subscribers": c["statistics"].get("subscriberCount"), "views": c["statistics"].get("viewCount"),
            "videos": c["statistics"].get("videoCount"),
            "uploads_playlist": c["contentDetails"]["relatedPlaylists"]["uploads"]}


def _video_summary(v: dict) -> dict:
    s, st = v.get("snippet", {}), v.get("status", {})
    return {"id": v["id"], "title": s.get("title"), "published": s.get("publishedAt"),
            "privacy": st.get("privacyStatus"), "publish_at": st.get("publishAt"),
            "views": v.get("statistics", {}).get("viewCount"), "likes": v.get("statistics", {}).get("likeCount"),
            "duration": v.get("contentDetails", {}).get("duration"), "url": f"https://youtu.be/{v['id']}"}


def list_videos(limit: int = 25) -> list[dict]:
    """Most recent uploads, including private and scheduled ones."""
    uploads = channel()["uploads_playlist"]
    items = yt().playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=min(50, limit)).execute()
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    if not ids:
        return []
    vids = yt().videos().list(part="snippet,status,statistics,contentDetails", id=",".join(ids)).execute()
    return [_video_summary(v) for v in vids.get("items", [])]


def get_video(video_id: str) -> dict:
    r = yt().videos().list(part="snippet,status,statistics,contentDetails", id=video_id).execute()
    if not r.get("items"):
        raise ValueError(f"No video {video_id} on this channel")
    v = r["items"][0]
    return {**_video_summary(v), "description": v["snippet"].get("description"), "tags": v["snippet"].get("tags", []),
            "category_id": v["snippet"].get("categoryId"), "made_for_kids": v["status"].get("selfDeclaredMadeForKids")}


def list_playlists() -> list[dict]:
    r = yt().playlists().list(part="snippet,status,contentDetails", mine=True, maxResults=50).execute()
    return [{"id": p["id"], "title": p["snippet"]["title"], "privacy": p["status"]["privacyStatus"],
             "count": p["contentDetails"]["itemCount"]} for p in r.get("items", [])]


def analytics(video_id: str | None = None, days: int = 28, top: int = 10) -> list[dict]:
    """Views, watch time, average view % (retention) per video for the last `days`."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    q = dict(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
             metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
             dimensions="video", sort="-views", maxResults=top)
    if video_id:
        q["filters"] = f"video=={video_id}"
    r = yta().reports().query(**q).execute()
    cols = [h["name"] for h in r.get("columnHeaders", [])]
    return [dict(zip(cols, row)) for row in r.get("rows", [])]


# ---------------------------------------------------------------- write

def update_video(video_id: str, title: str | None = None, description: str | None = None,
                 tags: list[str] | None = None, category_id: str | None = None) -> dict:
    v = yt().videos().list(part="snippet", id=video_id).execute()["items"][0]
    sn = v["snippet"]
    if title is not None:
        sn["title"] = title[:100]
    if description is not None:
        sn["description"] = description[:5000]
    if tags is not None:
        sn["tags"] = tags
    if category_id is not None:
        sn["categoryId"] = category_id
    body = {"id": video_id, "snippet": {k: sn[k] for k in ("title", "description", "tags", "categoryId") if k in sn}}
    yt().videos().update(part="snippet", body=body).execute()
    return get_video(video_id)


def _status(video_id: str, **changes) -> dict:
    st = yt().videos().list(part="status", id=video_id).execute()["items"][0]["status"]
    keep = {k: st[k] for k in ("privacyStatus", "publishAt", "selfDeclaredMadeForKids", "embeddable",
                               "license", "publicStatsViewable", "containsSyntheticMedia") if k in st}
    keep.update({k: v for k, v in changes.items() if v is not None})
    if keep.get("privacyStatus") != "private":
        keep.pop("publishAt", None)
    yt().videos().update(part="status", body={"id": video_id, "status": keep}).execute()
    return get_video(video_id)


def schedule(video_id: str, publish_at: str) -> dict:
    """Schedule a private video to go public at `publish_at` (ISO 8601 with offset, e.g.
    2026-10-12T19:00:00-04:00)."""
    when = dt.datetime.fromisoformat(publish_at)
    if when.tzinfo is None:
        raise ValueError("publish_at needs a timezone offset, e.g. 2026-10-12T19:00:00-04:00")
    if when <= dt.datetime.now(dt.timezone.utc):
        raise ValueError("publish_at is in the past")
    return _status(video_id, privacyStatus="private", publishAt=when.astimezone(dt.timezone.utc).isoformat())


def set_visibility(video_id: str, privacy: str) -> dict:
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError("privacy must be private, unlisted or public")
    return _status(video_id, privacyStatus=privacy)


def set_audience(video_id: str, made_for_kids: bool = False, synthetic_media: bool | None = None) -> dict:
    return _status(video_id, selfDeclaredMadeForKids=made_for_kids, containsSyntheticMedia=synthetic_media)


def set_thumbnail(video_id: str, image_path: str) -> dict:
    from googleapiclient.http import MediaFileUpload
    yt().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(image_path)).execute()
    return {"video": video_id, "thumbnail": os.path.basename(image_path)}


def playlist_id(title: str, description: str = "", privacy: str = "public") -> str:
    for p in list_playlists():
        if p["title"].lower() == title.lower():
            return p["id"]
    r = yt().playlists().insert(part="snippet,status", body={
        "snippet": {"title": title, "description": description}, "status": {"privacyStatus": privacy}}).execute()
    return r["id"]


def add_to_playlist(video_id: str, playlist: str) -> dict:
    """`playlist` is an id or a title (created if missing)."""
    pid = playlist if playlist.startswith("PL") else playlist_id(playlist)
    yt().playlistItems().insert(part="snippet", body={
        "snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
    return {"video": video_id, "playlist": pid}


def upload_captions(video_id: str, srt_path: str, language: str = "en", name: str = "English") -> dict:
    from googleapiclient.http import MediaFileUpload
    r = yt().captions().insert(part="snippet", body={
        "snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}},
        media_body=MediaFileUpload(srt_path, mimetype="application/octet-stream")).execute()
    return {"video": video_id, "caption": r["id"]}


def upload(path: str, title: str, description: str = "", tags: list[str] | None = None,
           privacy: str = "private", publish_at: str | None = None, category_id: str = "27",
           made_for_kids: bool = False, synthetic_media: bool = False, thumbnail: str | None = None,
           playlist: str | None = None, captions: str | None = None) -> dict:
    """Resumable upload + optional thumbnail, playlist, captions and schedule in one call."""
    from googleapiclient.http import MediaFileUpload
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": made_for_kids,
              "containsSyntheticMedia": synthetic_media}
    if publish_at:
        status["publishAt"] = dt.datetime.fromisoformat(publish_at).astimezone(dt.timezone.utc).isoformat()
    req = yt().videos().insert(part="snippet,status", body={
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags or [],
                    "categoryId": category_id}, "status": status},
        media_body=MediaFileUpload(path, chunksize=8 << 20, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    out = {"id": vid, "url": f"https://youtu.be/{vid}", "note": UNVERIFIED_UPLOAD_NOTE}
    for step, fn in (("thumbnail", lambda: thumbnail and set_thumbnail(vid, thumbnail)),
                     ("playlist", lambda: playlist and add_to_playlist(vid, playlist)),
                     ("captions", lambda: captions and upload_captions(vid, captions))):
        try:
            fn()
        except Exception as e:  # the video is up; report partial failures instead of raising
            out[f"{step}_error"] = str(e)[:300]
    return out
