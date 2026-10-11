# Research notes (Oct 2026)

What the system is designed around, and where each decision comes from. Vendor blogs dominate
this space, so numbers below are treated as hypotheses to check against your own Studio analytics.

## 1. Hooks and retention (long-form)

- **Three-phase opening.** Pattern interrupt (0-5 s), a *specific* payoff promise (5-15 s), a
  commitment hook (15-30 s). [prepublish.ai](https://prepublish.ai/guides/first-30-seconds)
- **The first 30 s is measured.** Studio reports it as the *Intro* key moment, so it is the first
  number to watch per video. [socialrails](https://socialrails.com/blog/youtube-audience-retention-complete-guide)
- **No greetings, no logo stings.** Lead with the intriguing statement inside 3 s.
  [1of10](https://1of10.com/blog/how-to-hook-viewers-in-the-first-30-seconds-of-a-youtube-video/)
- **Don't over-promise.** High CTR + a cliff in the first 30 s = packaging the video can't pay off.
  [prepublish.ai benchmarks](https://prepublish.ai/blog/youtube-retention-benchmarks-2026)
- **Second hook near 25-30 s**, then keep the curve flat by bridging the hook's energy into the
  story instead of resetting it. [marketeze](https://www.marketeze.ai/blog/youtube-longform-hooks-how-to-keep-viewers-past-the-first-30-seconds)
- **Vary pacing in the body**; slow down on visuals and emotional beats.
  [air.io](https://air.io/en/youtube-hacks/advanced-retention-editing-cutting-patterns-that-keep-viewers-past-minute-8)

**How Framewright applies it** (see `framewright/prompts.py`):
cold open from the most dramatic moment → one-line promise of what the viewer will understand →
stakes → chapters that each end on an open loop into the next ("re-hooks") → payoff that answers the
cold open → one-line bridge to the next video. Banned: greetings, "in this video", "subscribe",
cliché words. The Shorts format keeps the channel's ending-first hook.

## 2. Voice (free)

- **Kokoro-82M**: Apache-2.0, ~82M params, runs offline on CPU faster than real time; calm, even
  delivery that suits narration; weaker on numbers, abbreviations and rare names, so the script is
  pre-processed (respellings). [localaimaster](https://localaimaster.com/blog/kokoro-tts-local-setup),
  [kompozy review](https://kompozy.io/reviews/kokoro-tts), [openvoxai](https://openvoxai.com/blog/best-tts-models-local-cloud-2026)
- **edge-tts** stays as the zero-install option (cloud, free, more expressive range).
- Default "soothing" presets: slightly slower than neutral, lower pitch on edge voices, longer
  scene gaps. Users should A/B on their own script (`samples/`).

## 3. Visual relevance

Search ranking alone often returns the wrong subject (a query for a person returns the concert hall
named after them). Framewright re-ranks candidates with **CLIP** (open_clip ViT-B-32, CPU) against
each narration line + keywords, rejects near-duplicates, and only then downloads the full-size file.

## 4. Publishing via the YouTube Data API

- Uploads (`videos.insert`) from **unverified API projects created after 28 Jul 2020 are locked
  private** until the project passes Google's compliance audit; setting `privacyStatus=public`
  does not override it. [Google docs](https://developers.google.cn/youtube/v3/docs/videos?hl=en),
  [ayrshare](https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/)
- Quota for uploads is reported differently across sources (100-1,600 units); check your Cloud
  Console. [postproxy](https://postproxy.dev/blog/automate-youtube-uploads/)
- Testing-mode OAuth apps need your account added as a test user, otherwise "Access blocked".
  Custom thumbnails need a phone-verified channel.
  [glama: youtube-mcp](https://glama.ai/mcp/servers/miller-joe/youtube-mcp)

**Consequence:** the connector updates metadata, thumbnails, playlists and schedules on any video
(those calls aren't audit-locked), and can upload, but tells you when an upload will stay private.
Until the audit passes, upload in Studio (or via the browser agent) and let the connector do the rest.

## 5. Posting cadence

Two uploads a day (US late morning + evening, Eastern), Fri-Sun strongest; adjust from Studio >
Analytics > Audience > "When your viewers are on YouTube" after ~10 uploads.
