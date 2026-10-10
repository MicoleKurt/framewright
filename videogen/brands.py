"""Channel presets: the on-video lockup/end card and thumbnail kicker use these.

Real channel presets stay private: put them in local/brands.local.json (gitignored), e.g.
{"my-channel": {"name": "My Channel", "tagline": "My tagline"}}
"""
import json
import os

BRANDS = {
    "example": {"name": "Example Channel", "tagline": "New story daily"},
}

_LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local", "brands.local.json")
if os.path.exists(_LOCAL):
    with open(_LOCAL, encoding="utf-8") as f:
        BRANDS.update(json.load(f))
