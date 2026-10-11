"""Cheap grounding check: numbers and years in the narration must appear in the source text.

Local models invent dates far more often than they invent whole events, so this catches most
hallucinations for almost no cost. It cannot verify claims without numbers.
"""
import re

NUM = re.compile(r"\b\d[\d,.]*\b")


def _norm(n: str) -> str:
    return n.replace(",", "").rstrip(".")


def unsupported(text: str, source: str) -> list[str]:
    have = {_norm(n) for n in NUM.findall(source)}
    return [n for n in NUM.findall(text) if _norm(n) not in have and len(_norm(n)) > 1]


def clean(paragraph: str, source: str) -> tuple[str, list[str]]:
    """Drop sentences that contain numbers the source doesn't. Returns (text, dropped sentences)."""
    if not source:
        return paragraph, []
    sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    keep, dropped = [], []
    for s in sentences:
        (dropped if unsupported(s, source) else keep).append(s)
    return " ".join(keep), dropped
