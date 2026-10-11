# Music library

Put tracks you are licensed to use in this folder and list them in `library.json`:

```json
[
  {"file": "night-archive.mp3", "moods": ["mysterious", "tense"], "license": "YouTube Audio Library", "credit": ""},
  {"file": "long-road.mp3", "moods": ["somber", "calm"], "license": "CC BY 4.0", "credit": "Kevin MacLeod (incompetech.com)"}
]
```

Moods: `mysterious`, `tense`, `somber`, `calm`, `uplifting`, `triumphant`, `epic`. The script picks a
mood; the closest track is looped/trimmed under the narration and ducked when the voice speaks.
A non-empty `credit` is added to the video description automatically.

Free sources: YouTube Studio > Audio library, Pixabay Music, incompetech.com (credit required).
Audio files here are gitignored. With no match, iframesco generates an ambient pad.
