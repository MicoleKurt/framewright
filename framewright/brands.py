"""Channel presets (brand templates): name, tagline, accent colour, serif font, default voice/format.

They drive the on-video lockup/end card, chapter cards and thumbnails. Real channel presets stay
private: put them in local/brands.local.json (gitignored), e.g.

    {"my-channel": {"name": "My Channel", "tagline": "New story daily", "accent": "#C88F3B",
                    "font_serif": "Georgia", "voice": "soothing", "format": "long"}}
"""
import json
import os

BRANDS = {
    "example": {"name": "Example Channel", "tagline": "New story daily", "accent": "#C88F3B",
                "font_serif": "Georgia"},
    "noir": {"name": "Noir Files", "tagline": "True stories, told slowly", "accent": "#B23A3A",
             "font_serif": "Georgia", "voice": "storyteller", "format": "long"},
    "atlas": {"name": "Atlas Minute", "tagline": "The world in sixty seconds", "accent": "#3FA7D6",
              "font_serif": "Georgia", "voice": "energetic", "format": "short"},
}

# repo-local, then the folder you run from (a private channel workspace), then FW_BRANDS
for _path in dict.fromkeys([
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local", "brands.local.json"),
        os.path.join(os.getcwd(), "local", "brands.local.json"), os.getenv("FW_BRANDS", "")]):
    if _path and os.path.exists(_path):
        with open(_path, encoding="utf-8") as f:
            BRANDS.update(json.load(f))
