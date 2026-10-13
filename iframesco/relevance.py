"""Footage relevance scoring with CLIP: rank candidate visuals against the narration line.

Search engines return the right *words*, not always the right *picture* (a query for a person
returns the building named after them). CLIP embeds the line and each candidate preview in the same
space; we keep the best matches and skip near-duplicates of shots already used.

Optional: needs `open_clip_torch` (CPU is fine, ~40 ms per image). Without it, search order wins.
"""
import io
import os
from functools import lru_cache

from . import research

MODEL = os.getenv("FS_CLIP_MODEL", "ViT-B-32")
PRETRAINED = os.getenv("FS_CLIP_WEIGHTS", "laion2b_s34b_b79k")
DUP = 0.90  # cosine similarity above which two shots count as the same picture

# Archive searches surface old material that must never reach a video. Titles are checked first (cheap),
# then CLIP compares each image against these descriptions and drops anything that matches them better
# than it matches the narration.
BLOCKED_WORDS = ("minstrel", "blackface", "caricature", "racist", "racism", "sambo", "golliwog", "darkey",
                 "darky", "coon", "pickaninny", "nude", "naked", "erotic", "nsfw", "gore", "corpse",
                 "lynching", "swastika", "propaganda")
UNSAFE = ("a racist caricature cartoon", "a minstrel show poster", "a blackface performer",
          "a nude person", "a dead body", "graphic violence and blood")
OFF_TOPIC = {  # weak shots for a story: allowed only when the line asks for them
    "map": "a map", "plan": "an architectural plan or technical drawing", "diagram": "a diagram",
    "document": "a page of printed text", "logo": "a logo on a plain background",
}
OFF_TOPIC_PENALTY = 0.04


def available() -> bool:
    if os.getenv("FS_CLIP", "1") == "0":
        return False
    from importlib.util import find_spec  # cheap: don't import torch just to check
    return find_spec("open_clip") is not None and find_spec("torch") is not None


@lru_cache(maxsize=1)
def _model():
    import open_clip
    import torch
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL, pretrained=PRETRAINED)
    model.eval()
    torch.set_grad_enabled(False)
    return model, preprocess, open_clip.get_tokenizer(MODEL)


@lru_cache(maxsize=256)
def _embed_text(text: str):
    import torch
    model, _, tok = _model()
    e = model.encode_text(tok([text[:300]]))
    return torch.nn.functional.normalize(e, dim=-1)[0]


def _embed_images(blobs: list[bytes]):
    import torch
    from PIL import Image
    model, preprocess, _ = _model()
    batch = torch.stack([preprocess(Image.open(io.BytesIO(b)).convert("RGB")) for b in blobs])
    return torch.nn.functional.normalize(model.encode_image(batch), dim=-1)


def blocked(candidate: dict) -> bool:
    """True when the file title or description names something that must not appear on screen."""
    text = " ".join(str(candidate.get(k, "")) for k in ("title", "description", "url")).lower()
    return any(w in text for w in BLOCKED_WORDS)


def _penalties(img, text: str):
    """Per-image score adjustment: -1 for unsafe matches, a small penalty for off-topic visuals."""
    import torch
    unsafe = torch.stack([_embed_text(t) for t in UNSAFE])
    worst = (img @ unsafe.T).max(dim=1).values
    lowered = text.lower()
    off = [t for word, t in OFF_TOPIC.items() if word not in lowered]
    off_sim = (img @ torch.stack([_embed_text(t) for t in off]).T).max(dim=1).values if off else None
    return worst, off_sim


class Ranker:
    """Keeps the embeddings of shots already used, so later scenes don't repeat a picture."""

    def __init__(self) -> None:
        self.used = []

    def rank(self, text: str, candidates: list[dict], keep: int) -> list[dict]:
        if not candidates:
            return []
        if not available():
            return candidates[:keep]
        candidates = [c for c in candidates if not blocked(c)]
        if not candidates:
            return []
        scored = []
        blobs, idx = [], []
        for i, c in enumerate(candidates):
            b = research.fetch_bytes(c.get("preview") or (c["url"] if c["kind"] == "image" else ""))
            if b:
                blobs.append(b)
                idx.append(i)
        if not blobs:
            return candidates[:keep]
        try:
            img = _embed_images(blobs)
        except Exception as e:  # a corrupt preview must not stop the render
            print(f"[relevance] embedding failed: {e}")
            return candidates[:keep]
        sims = (img @ _embed_text(text)).tolist()
        worst, off_sim = _penalties(img, text)
        for j, i in enumerate(idx):
            if float(worst[j]) > max(sims[j], 0.22):  # looks more like an unsafe image than the line
                print(f"[relevance] dropped unsafe-looking image: {candidates[i].get('title', candidates[i].get('url'))}")
                continue
            score = sims[j]
            if off_sim is not None and float(off_sim[j]) > sims[j]:
                score -= OFF_TOPIC_PENALTY
            scored.append((score, i, img[j]))
        scored.sort(key=lambda s: -s[0])
        out = []
        for score, i, emb in scored:
            if any(float(emb @ u) > DUP for u in self.used):
                continue
            c = dict(candidates[i], score=round(score, 3))
            out.append(c)
            self.used.append(emb)
            if len(out) == keep:
                break
        return out
