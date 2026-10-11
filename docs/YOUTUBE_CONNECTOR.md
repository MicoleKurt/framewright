# YouTube connector (MCP server + CLI)

Lets Claude (or any MCP client) read and manage **your own** channel: list videos, edit titles,
descriptions and tags, schedule, set thumbnails, playlists, captions, read retention analytics,
upload renders, and queue new iframesco renders. Free: it uses your own Google Cloud project's
YouTube Data API quota.

## 1. One-time Google setup (~5 minutes, done by the channel owner)

1. Open <https://console.cloud.google.com/>, create a project (e.g. "iframesco").
2. **APIs & Services > Library**: enable **YouTube Data API v3** and **YouTube Analytics API**.
3. **APIs & Services > OAuth consent screen**: User type *External*, app name "iframesco",
   your email; add yourself under **Test users**.
4. **APIs & Services > Credentials > Create credentials > OAuth client ID**: type **Desktop app**.
   Download the JSON and save it as `~/.iframesco/client_secret.json`
   (Windows: `C:\Users\<you>\.iframesco\client_secret.json`).
5. Connect your channel (opens a browser consent page once; the token is stored in `~/.iframesco/`):

```bash
iframesco youtube auth
```

Pick the Google account / **brand account** that owns the channel on the consent screen.

## 2. Add it to Claude Code

```bash
claude mcp add youtube -- python -m iframesco.mcp_server
```

or, after `pip install -e ".[youtube]"`, `claude mcp add youtube -- iframesco-mcp`.
For the project only, add `--scope project` (writes `.mcp.json`).

Tools: `channel_overview`, `list_videos`, `get_video`, `list_playlists`, `video_analytics`,
`update_video`, `schedule_video`, `set_visibility`, `set_audience`, `set_thumbnail`, `add_to_playlist`,
`upload_captions`, `upload_render`, `create_video`, `job_status`.

Keep the write tools on "ask" in your permission settings: they change a live channel.

## 3. CLI equivalents

```bash
iframesco youtube channel
iframesco youtube videos 10
iframesco youtube update VIDEO_ID '{"title": "New title"}'
iframesco youtube schedule VIDEO_ID 2026-10-12T19:00:00-04:00
iframesco youtube thumbnail VIDEO_ID output/my-video.thumb.jpg
iframesco youtube playlist VIDEO_ID "Origin Stories"
iframesco youtube analytics
iframesco youtube upload output/my-video-long-123.mp4 2026-10-13T11:00:00-04:00
```

## Limits worth knowing

- **Uploads from an unaudited project stay private.** YouTube locks `videos.insert` uploads from
  projects that haven't passed its API compliance audit. Everything else (edit, schedule an
  existing video, thumbnails, playlists, captions, analytics) works. Until the audit passes, upload
  in Studio and let the connector finish the job, or apply for the audit in the Cloud Console.
- **Custom thumbnails** need a phone-verified channel. Shorts only accept 9:16 thumbnails.
- **Quota**: 10,000 units/day by default. Reads cost ~1 unit, updates ~50, captions ~400,
  uploads more (Google has changed the upload cost; check your Cloud Console quota page).
- "Access blocked" on the consent screen = your account isn't listed as a test user.
