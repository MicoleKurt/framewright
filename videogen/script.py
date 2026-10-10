"""Turn research into a scene-by-scene narration script using a local LLM (Ollama).

Two calls on purpose: small models write terse fragments when forced into JSON, but write
natural narration as plain prose. So: (1) prose paragraphs = scenes, (2) JSON image queries.
"""
import json
import os
import re
import requests

OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "0"))  # 0 = CPU; -1 lets Ollama pick the GPU

NARRATION_PROMPT = """Write the narration for a short documentary video about: {topic}
Use only these facts. Do not invent dates or numbers:
{facts}

Write exactly {n} paragraphs separated by blank lines. Each paragraph is 2 sentences,
20 to 35 words, spoken by a calm documentary narrator, with a concrete detail (a place, a date,
a person). Paragraph 1 opens with the most surprising fact. The last paragraph ends the story
with a clear closing line. No headings, no numbering, no questions, no exclamation marks.
Avoid: "fascinating", "journey", "delve", "tapestry", "testament", "in a world"."""

QUERIES_PROMPT = """For each numbered narration line below, give 2 image search queries of 2-4 words
for finding a matching photograph. Queries must be concrete and photographable, and include the
subject "{subject}" or a specific place/object named in the line. Never abstract ideas.
{lines}
Reply with JSON only: {{"queries": [[str, str], ...]}} with exactly {n} pairs, in order."""

BANNED = re.compile(r"\b(fascinating|journey|delve|tapestry|testament)\b", re.I)


def _ask(prompt: str, json_mode: bool = False, temperature: float = 0.6) -> str:
    options = {"temperature": temperature, **({"num_gpu": NUM_GPU} if NUM_GPU >= 0 else {})}
    body = requests.post(f"{OLLAMA}/api/generate", timeout=600, json={
        "model": MODEL, "prompt": prompt, "stream": False, "options": options,
        **({"format": "json"} if json_mode else {}),
    }).json()
    if "error" in body:
        raise RuntimeError(body["error"][:200])
    return body["response"]


def _paragraphs(text: str) -> list[str]:
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    paras = [re.sub(r"^(\d+[.)]|[-*])\s*", "", p) for p in paras]  # strip stray numbering/bullets
    return [p for p in paras if len(p.split()) >= 8]


def write_script(topic: str, facts: dict, n_scenes: int = 6, attempts: int = 2) -> dict:
    title = facts["title"]
    for attempt in range(attempts):
        try:
            prose = _ask(NARRATION_PROMPT.format(topic=topic, facts=facts["text"][:3000] or "(none)",
                                                 n=n_scenes), temperature=0.6 + 0.1 * attempt)
            paras = _paragraphs(prose)[:n_scenes]
            cliches = [p for p in paras if BANNED.search(p)]
            paras = [p for p in paras if p not in cliches]  # drop a cliché line, keep the rest
            avg = sum(len(p.split()) for p in paras) / max(1, len(paras))
            if len(paras) < 3 or avg < 14:
                raise ValueError(f"weak script ({len(paras)} usable paragraphs, {avg:.0f} words each, "
                                 f"{len(cliches)} dropped for clichés)")
            return {"title": title, "source": "llm",
                    "scenes": _with_queries(paras, subject(topic, title))}
        except Exception as e:
            print(f"[script] attempt {attempt + 1} failed: {e}")
    print("[script] using Wikipedia fallback")
    return _fallback(topic, facts, n_scenes)


def _with_queries(paras: list[str], subj: str) -> list[dict]:
    lines = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(paras))
    try:
        pairs = json.loads(_ask(QUERIES_PROMPT.format(subject=subj, lines=lines, n=len(paras)),
                                json_mode=True, temperature=0.3)).get("queries", [])
    except Exception as e:
        print(f"[script] query generation failed ({e}); using subject only")
        pairs = []
    scenes = []
    for i, p in enumerate(paras):
        q = pairs[i] if i < len(pairs) and isinstance(pairs[i], list) else []
        scenes.append({"narration": p, "keywords": [k for k in q if isinstance(k, str)][:2] or [subj]})
    return scenes


def _fallback(topic: str, facts: dict, n: int) -> dict:
    sentences = re.split(r"(?<=[.!?])\s+", facts["text"].strip())
    sentences = [s for s in sentences if 20 < len(s) < 220][:n] or [f"This is a short film about {topic}."]
    subj = subject(topic, facts["title"])
    return {"title": facts["title"], "source": "fallback",
            "scenes": [{"narration": s, "keywords": [subj]} for s in sentences]}


STOP = {"the", "a", "an", "of", "history", "story", "rise", "fall", "how", "why", "what", "and", "in", "to"}


def subject(topic: str, title: str) -> str:
    """Core noun phrase used to anchor image searches: 'the history of coffee' -> 'coffee'."""
    words = [w for w in re.findall(r"[a-zA-Z0-9']+", title or topic) if w.lower() not in STOP]
    return " ".join(words[:3]) or topic
