"""Output formats. A Short and a long-form video differ in canvas, pacing, captions and packaging."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    name: str
    w: int
    h: int
    orientation: str          # stock-footage search filter
    burn_captions: bool       # karaoke captions on the video itself
    caption_words: int        # words per caption phrase
    shots_per_scene: int      # visuals per narration paragraph
    crossfade: float          # seconds of overlap between shots
    scene_gap: float          # silence after each paragraph
    thumb: tuple[int, int]

    @property
    def vertical(self) -> bool:
        return self.h > self.w


SHORT = Format("short", 1080, 1920, "portrait", True, 4, 2, 0.35, 0.5, (1080, 1920))
LONG = Format("long", 1920, 1080, "landscape", False, 7, 2, 0.6, 0.7, (1280, 720))

FORMATS = {f.name: f for f in (SHORT, LONG)}


def get(name: str | None) -> Format:
    return FORMATS.get((name or "short").lower(), SHORT)
