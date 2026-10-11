# iframesco: build spec

> The brief this version was built from. Free to run: no paid APIs, everything works on a laptop.

## Goal

Topic (or a hand-written script) in → a publish-ready YouTube video out, in either format:

| | Short | Long-form |
|---|---|---|
| Canvas | 1080x1920 | 1920x1080 |
| Length | 30-60 s, 4-8 scenes | 6-15 min, 5-8 chapters, 30-90 scenes |
| Captions | burned-in karaoke | `.srt` sidecar (+ optional burned lower-third) |
| Extras | cover 1080x1920 | thumbnail 1280x720, chapter timestamps in the description |

## Pipeline

1. **Research**: full Wikipedia article (not just the intro) as the fact source.
2. **Script** (local LLM via Ollama, default `qwen3:8b`):
   outline JSON (titles, thumbnail hook, cold open, chapters + beats) → chapter prose →
   image queries per paragraph → metadata. Prompts live in `iframesco/prompts.py`.
3. **Fact check**: every year/number in the narration must appear in the source text; failing
   sentences are dropped (LLM path) or reported (human scripts).
4. **Voice**: Kokoro (offline) or edge-tts; soothing presets; respelling map for hard names;
   word-level timings for captions.
5. **Media**: Pexels + Pixabay stock video (free keys) and Wikimedia Commons stills; candidates
   re-ranked with CLIP; near-duplicates rejected; attribution collected.
6. **Render**: Ken Burns on stills, crossfades between shots, film grade, mood music (local
   licensed library, generated pad as fallback), NVENC when available.
7. **Package**: `.mp4`, thumbnail(s), `.youtube.json` (title/description/tags/chapters), `.srt`,
   credits.
8. **Publish**: YouTube connector (MCP server + CLI) for metadata, thumbnails, playlists,
   schedules, analytics, and uploads.

## Platform

- **Job queue**: SQLite-backed, survives restarts, N workers (`FS_WORKERS`, default 1).
- **Storage**: local `output/`; optional S3 mirror when `FS_S3_BUCKET` is set.
- **Brands**: per-channel accent colour, fonts, kicker/tagline, intro/outro cards.
- **UI**: one page: create (format, length, voice, brand), queue, preview, script/chapters,
  copy-ready metadata.

## Non-goals (for now)

TikTok auto-posting (its Content Posting API needs app review), paid LLM/TTS APIs, voice cloning.
