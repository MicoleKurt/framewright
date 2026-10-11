"""Output formats. A Short and a long-form video differ in canvas, pacing, captions and packaging."""
import dataclasses
import os
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
    # px of the frame the platform's own UI covers (Shorts: search/camera on top, channel handle,
    # title and description at the bottom, like/comment/share on the right). See docs/RESEARCH.md.
    safe_top: int = 0
    safe_bottom: int = 0
    safe_right: int = 0

    @property
    def vertical(self) -> bool:
        return self.h > self.w

    def layout(self) -> dict:
        """Where burned-in text goes on a vertical canvas. Everything is derived from the safe
        zone so captions, the title card and the end card cannot drift into the platform UI.

        From the bottom up: [platform UI] > gap > captions (2 lines) > gap > title/end card.
        """
        cap_font, line = 70, 88  # px; line height incl. leading
        cap_bottom = self.h - (self.safe_bottom + 20)          # text baseline area ends here
        cap_top = cap_bottom - 2 * line                        # two-line phrase
        kicker_edge = cap_top - 40                             # small brand line sits just above
        kicker_v = self.h - kicker_edge
        lockup_v = kicker_v + 55
        return {
            "cap_font": cap_font, "cap_margin_v": self.h - cap_bottom,
            "cap_margin_h": max(120, self.safe_right), "cap_top": cap_top, "cap_bottom": cap_bottom,
            "kicker_v": kicker_v, "lockup_v": lockup_v,
            "rule_y": self.h - lockup_v - 122, "rule_x": (self.w - 140) // 2,
        }


SHORT = Format("short", 1080, 1920, "portrait", True, 4, 2, 0.35, 0.5, (1080, 1920),
               safe_top=250, safe_bottom=580, safe_right=150)
LONG = Format("long", 1920, 1080, "landscape", False, 7, 2, 0.6, 0.7, (1280, 720))

FORMATS = {f.name: f for f in (SHORT, LONG)}


SAFE_ENV = {"safe_top": "FS_SAFE_TOP", "safe_bottom": "FS_SAFE_BOTTOM", "safe_right": "FS_SAFE_RIGHT"}


def get(name: str | None) -> Format:
    """The format, with the platform safe zone optionally overridden (px) via FS_SAFE_TOP /
    FS_SAFE_BOTTOM / FS_SAFE_RIGHT, e.g. FS_SAFE_BOTTOM=480 for a tighter reserve."""
    fmt = FORMATS.get((name or "short").lower(), SHORT)
    over = {k: int(os.environ[v]) for k, v in SAFE_ENV.items() if os.environ.get(v, "").isdigit()}
    return dataclasses.replace(fmt, **over) if over and fmt.vertical else fmt
