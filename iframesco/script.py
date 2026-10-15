"""Turn research into a scene-by-scene script with a local LLM (Ollama). Free, offline.

Small models write terse fragments when forced into JSON but natural narration as prose, so prose
and structure are separate calls: JSON for plans/queries, plain text for narration.
"""
import json
import os
import re

import requests

from . import factcheck, prompts, research
from .music import MOODS

OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
# 0 = CPU (safe default: Ollama GPU runners crash on NVIDIA drivers < 570); -1 = let Ollama use the GPU
NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "0"))
WPM = 140  # narration speed of the soothing presets

BANNED = re.compile(r"\b(" + "|".join(re.escape(w) for w in prompts.BANNED_WORDS) + r")\b", re.I)


FALLBACKS = ["qwen3:8b", "hf.co/Qwen/Qwen3-8B-GGUF:Q4_K_M", "qwen3:14b", "qwen2.5:7b", "llama3.1:8b", "gemma3:4b", "qwen2.5:3b"]
_resolved: str | None = None


def model() -> str:
    """The configured model if Ollama has it, else the best installed fallback."""
    global _resolved
    if _resolved:
        return _resolved
    try:
        have = {m["name"] for m in requests.get(f"{OLLAMA}/api/tags", timeout=10).json().get("models", [])}
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(f"Ollama is not reachable at {OLLAMA} ({e}). Start it, or pass --script.") from e
    for name in [MODEL, *FALLBACKS]:
        if name in have or f"{name}:latest" in have:
            if name != MODEL:
                print(f"[script] {MODEL} not installed; using {name} (ollama pull {MODEL} for better scripts)")
            _resolved = name
            return name
    raise RuntimeError(f"No usable Ollama model. Run: ollama pull {MODEL}")


def ask(prompt: str, json_mode: bool = False, temperature: float = 0.6, ctx: int = 8192,
        max_tokens: int = 2048) -> str:
    options = {"temperature": temperature, "num_ctx": ctx, "num_predict": max_tokens,
               **({"num_gpu": NUM_GPU} if NUM_GPU >= 0 else {})}
    name = model()
    body = requests.post(f"{OLLAMA}/api/generate", timeout=900, json={
        "model": name, "prompt": prompt, "stream": False, "options": options,
        **({"think": False} if "qwen3" in name.lower() else {}),
        **({"format": "json"} if json_mode else {}),
    }).json()
    if "error" in body:
        raise RuntimeError(body["error"][:200])
    return re.sub(r"<think>.*?</think>", "", body["response"], flags=re.S).strip()


LABEL = re.compile(r"^\s*(the\s+)?(promise|stakes|payoff|hook|cold open|chapter\s*\d*|paragraph\s*\d*)\s*[:.\-]\s*", re.I)


def _paragraphs(text: str, min_words: int = 8) -> list[str]:
    paras = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        # a short line without end punctuation is a heading the model added ("Oxygen Tank Exploded")
        lines = [ln for ln in lines if not (len(ln.split()) <= 8 and not re.search(r"[.!?\"')]$", ln))]
        p = re.sub(r"\s+", " ", " ".join(lines)).strip()
        p = LABEL.sub("", re.sub(r"^(\d+[.)]|[-*#]+)\s*", "", p))  # numbering, bullets, "Promise:" labels
        if len(p.split()) >= min_words:
            paras.append(p)
    return paras


def _norm(sentence: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip()


def _clean(paras: list[str], source: str, report: list, seen: set | None = None) -> list[str]:
    """Drop sentences that use banned filler, repeat earlier narration (8B models love to copy the
    'previous paragraph' they were given), or contain numbers the source doesn't."""
    seen = set() if seen is None else seen
    out = []
    for p in paras:
        keep = []
        for sent in re.split(r"(?<=[.!?])\s+", p.strip()):
            key = _norm(sent)
            if not key or key in seen or BANNED.search(sent):
                continue
            seen.add(key)
            keep.append(sent)
        p, dropped = factcheck.clean(" ".join(keep), source)
        report.extend(dropped)
        if len(p.split()) >= 8:
            out.append(p)
    return out


STOP = {"the", "a", "an", "of", "history", "story", "rise", "fall", "how", "why", "what", "and", "in", "to"}


def subject(topic: str, title: str) -> str:
    """Core noun phrase used to anchor image searches: 'the history of coffee' -> 'coffee'."""
    words = [w for w in re.findall(r"[a-zA-Z0-9']+", title or topic) if w.lower() not in STOP]
    return " ".join(words[:3]) or topic


def with_queries(paras: list[str], subj: str) -> list[dict]:
    scenes = []
    for start in range(0, len(paras), 12):  # batches keep the JSON small enough for 8B models
        batch = paras[start:start + 12]
        lines = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(batch))
        try:
            pairs = json.loads(ask(prompts.QUERIES.format(subject=subj, lines=lines, n=len(batch)),
                                   json_mode=True, temperature=0.3)).get("queries", [])
        except Exception as e:
            print(f"[script] query generation failed ({e}); using subject only")
            pairs = []
        for i, p in enumerate(batch):
            q = pairs[i] if i < len(pairs) and isinstance(pairs[i], list) else []
            scenes.append({"narration": p, "keywords": [k for k in q if isinstance(k, str)][:2] or [subj]})
    return scenes


# ---------------------------------------------------------------- Shorts

def pronoun(text: str) -> str:
    """'his' / 'her' / 'their' / 'its' for the closing line, from how the source refers to the subject."""
    t = " " + text[:4000].lower() + " "
    counts = {"his": t.count(" he ") + t.count(" his "), "her": t.count(" she ") + t.count(" her "),
              "their": t.count(" they ") + t.count(" their ")}
    best = max(counts, key=counts.get)
    return best if counts[best] >= 3 else "its"


def pick_images(paras: list[str], article: str, subj: str) -> list[dict]:
    """Choose photos from the subject's Wikipedia article for each line; search queries fill the gaps."""
    pool = research.wiki_images(article, 40) if article else []
    picks: list = []
    if pool:
        images = "\n".join(f"{i + 1}. {c['title']} - {c.get('description', '')[:110]}" for i, c in enumerate(pool))
        lines = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(paras))
        try:
            picks = json.loads(ask(prompts.IMAGE_PICK.format(lines=lines, images=images, n=len(paras)),
                                   json_mode=True, temperature=0.2, ctx=16384)).get("picks", [])
        except Exception as e:
            print(f"[script] image picking failed ({e}); using search queries")
    scenes, used = with_queries(paras, subj), {}
    for i, sc in enumerate(scenes):
        chosen = []
        for k in (picks[i] if i < len(picks) and isinstance(picks[i], list) else []):
            if isinstance(k, int) and 1 <= k <= len(pool) and used.get(k, 0) < 2:
                used[k] = used.get(k, 0) + 1
                chosen.append(f"file:{pool[k - 1]['title']}")
        if chosen:  # exact Wikipedia photos first, ranked search as the second shot when only one was picked
            sc["keywords"] = chosen[:2] if len(chosen) > 1 else chosen + [f"wiki:{article}"]
    return scenes


def package(paras: list[str], subj: str, facts: dict) -> dict:
    """Title, frame-1 hook, thumbnail line and tags, written from the finished narration."""
    try:
        meta = json.loads(ask(prompts.SHORT_PACKAGE.format(narration="\n\n".join(paras), subject=subj),
                              json_mode=True, temperature=0.5))
    except Exception as e:
        print(f"[script] packaging failed ({e})")
        meta = {}
    title = str(meta.get("title") or facts["title"])[:100]
    hook = str(meta.get("thumbnail_hook") or f"Before {subj}")
    first = str(meta.get("first_line") or paras[0])
    desc = f"{first}\n\nSource: {facts['title']}, Wikipedia ({facts.get('url', '')})"
    return {"hook_text": str(meta.get("hook_text") or "")[:40] or None,
            "thumbnail": {"label": subj, "hook": _two_lines(hook), "scene": 0},
            "youtube": {"title": title, "description": desc,
                        "tags": [t for t in meta.get("tags", []) if isinstance(t, str)][:15]}}


def write_short(topic: str, facts: dict, n_scenes: int = 5, attempts: int = 2) -> dict:
    title, report = facts["title"], []
    # origin stories live in the early sections; keep the prompt small enough for an 8B model
    src = _relevant(facts["text"], "early life childhood youth education career began first", 3500)         if len(facts["text"]) > 3500 else facts["text"]
    for attempt in range(attempts):
        try:
            prose = ask(prompts.SHORT_NARRATION.format(
                topic=topic, facts=src or "(none)", n=n_scenes, example=prompts.SHORT_EXAMPLE,
                pronoun=pronoun(facts["text"]), style=prompts.STYLE), temperature=0.6 + 0.1 * attempt)
            paras = _clean(_paragraphs(prose), facts["text"], report)[:n_scenes]
            if len(paras) < 3:
                raise ValueError(f"weak script ({len(paras)} usable paragraphs)")
            subj = subject(topic, title)
            plan = {"title": title, "subject": subj, "format": "short", "source": "llm",
                    "sources": [facts.get("url", "")], "factcheck_dropped": report,
                    "scenes": pick_images(paras, title, subj)}
            plan.update({k: v for k, v in package(paras, subj, facts).items() if v})
            return plan
        except Exception as e:
            print(f"[script] attempt {attempt + 1} failed: {e}")
    return fallback(topic, facts, n_scenes)


# ---------------------------------------------------------------- Long-form

def _sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"\n(==+ [^=]+ ==+)\n", "\n" + text)
    out = [("Intro", parts[0])]
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i].strip("= "), parts[i + 1]))
    return [(h, b.strip()) for h, b in out if b.strip()]


def _relevant(text: str, query: str, budget: int = 5000) -> str:
    """Pick the article sections that share the most words with the chapter plan."""
    words = {w for w in re.findall(r"[a-z]{4,}", query.lower())}
    ranked = sorted(_sections(text), key=lambda s: -len(words & set(re.findall(r"[a-z]{4,}", (s[0] + s[1]).lower()))))
    out = ""
    for head, body in ranked:
        if len(out) >= budget:
            break
        out += f"\n[{head}]\n{body[: budget - len(out)]}\n"
    return out.strip()


def outline(topic: str, facts: dict, minutes: int, chapters: int) -> dict:
    plan = json.loads(ask(prompts.OUTLINE.format(topic=topic, minutes=minutes, facts=facts["text"][:12000],
                                                 chapters=chapters, moods=", ".join(MOODS)),
                          json_mode=True, temperature=0.5, ctx=16384, max_tokens=2500))
    if not plan.get("chapters") or not plan.get("cold_open"):
        raise ValueError("outline missing chapters/cold_open")
    return plan


def write_long(topic: str, facts: dict, minutes: int = 10, progress=lambda m: None) -> dict:
    """Outline -> cold open -> chapters (each ending on an open loop) -> image queries -> metadata."""
    n_ch = max(4, min(8, round(minutes / 1.6)))
    words_total = minutes * WPM
    report: list[str] = []
    seen: set[str] = set()
    src = facts["text"]
    progress("Planning chapters")
    plan = outline(topic, facts, minutes, n_ch)
    chapters = plan["chapters"][:n_ch]
    subj = subject(topic, facts["title"])
    scenes: list[dict] = []

    progress("Writing cold open")
    cold = ask(prompts.COLD_OPEN.format(topic=topic, words=min(160, words_total // 8), facts=src[:6000],
                                        cold_open=plan["cold_open"], promise=plan.get("promise", ""),
                                        stakes=plan.get("stakes", ""), style=prompts.STYLE),
               ctx=12288, temperature=0.65)
    opening = _clean(_paragraphs(cold), src, report, seen)
    scenes += [{"narration": p} for p in opening]

    per_ch = (words_total - sum(len(p.split()) for p in opening)) // len(chapters)
    for k, ch in enumerate(chapters, start=1):
        progress(f"Writing chapter {k}/{len(chapters)}")
        last = k == len(chapters)
        ending = (prompts.CHAPTER_END_FINAL.format(payoff=plan.get("payoff", "")) if last
                  else prompts.CHAPTER_END_LOOP.format(open_loop=ch.get("open_loop", "")))
        beats = "\n".join(f"- {b}" for b in ch.get("beats", []))
        text = ask(prompts.CHAPTER.format(
            k=k, n=len(chapters), topic=topic, title=ch["title"], beats=beats,
            facts=_relevant(src, ch["title"] + " " + beats), previous=scenes[-1]["narration"] if scenes else "",
            words=per_ch, paras=max(2, round(per_ch / 55)), ending=ending, style=prompts.STYLE),
            ctx=12288, temperature=0.65, max_tokens=1600)
        paras = _clean(_paragraphs(text), src, report, seen)
        for i, p in enumerate(paras):
            scenes.append({"narration": p, **({"chapter": ch["title"]} if i == 0 else {})})

    progress("Choosing visuals")
    queried = with_queries([s["narration"] for s in scenes], subj)
    for s, q in zip(scenes, queried):
        s["keywords"] = q["keywords"]

    title = (plan.get("titles") or [facts["title"]])[0]
    hook = plan.get("thumbnail_hook") or facts["title"]
    desc = (f"{plan.get('promise', '')}\n\n{plan.get('stakes', '')}\n\n"
            f"Source: {facts['title']}, Wikipedia ({facts.get('url', '')})").strip()
    return {
        "title": facts["title"], "subject": subj, "format": "long", "source": "llm",
        "mood": plan.get("mood") if plan.get("mood") in MOODS else "mysterious",
        "sources": [facts.get("url", "")], "factcheck_dropped": report, "plan": plan,
        "scenes": scenes,
        "thumbnail": {"label": subj, "hook": _two_lines(hook), "scene": 0},
        "youtube": {"title": title[:100], "description": desc, "tags": plan.get("tags", [])[:15],
                    "title_options": plan.get("titles", [])},
    }


def _two_lines(hook: str) -> str:
    w = hook.split()
    return " ".join(w[: (len(w) + 1) // 2]) + "\n" + " ".join(w[(len(w) + 1) // 2:]) if len(w) > 2 else hook


def fallback(topic: str, facts: dict, n: int) -> dict:
    sentences = re.split(r"(?<=[.!?])\s+", facts["text"].strip())
    sentences = [s for s in sentences if 20 < len(s) < 220][:n] or [f"This is a short film about {topic}."]
    subj = subject(topic, facts["title"])
    return {"title": facts["title"], "subject": subj, "source": "fallback",
            "scenes": [{"narration": s, "keywords": [subj]} for s in sentences]}
