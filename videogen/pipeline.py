"""Orchestrates topic -> research -> script -> voice -> media -> render -> mp4."""
import json
import os
import re
import time
from typing import Callable

from . import render, research, script, voice, youtube

Progress = Callable[[str, float], None]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "video"


def _gather_media(scene: dict, idx: int, work: str, used: set, subject: str,
                  use_youtube: bool = False, credits: list | None = None) -> list[str]:
    """Up to 2 visuals per scene: a Creative Commons YouTube clip (opt-in), Pexels footage if
    keyed, else Commons photos. Queries are anchored to the subject so 'Ethiopia' doesn't
    return random landscapes."""
    files = []
    queries = [k if subject.lower() in k.lower() else f"{subject} {k}" for k in scene["keywords"]]
    if use_youtube:
        try:
            clip = youtube.cc_clip(queries[0], f"{work}/s{idx}_yt", used=used)
        except Exception as e:  # network / extractor breakage must not kill the render
            print(f"[youtube] search failed: {e}")
            clip = None
        if clip:
            files.append(clip.pop("path"))
            if credits is not None:
                credits.append(clip)
    for kw in dict.fromkeys(queries + [subject]):  # ordered de-dupe
        candidates = [(u, "mp4") for u in research.pexels_videos(kw, 2)] + \
                     [(u, "jpg") for u in research.commons_images(kw, 12)]
        for url, ext in candidates:
            if url in used:
                continue
            used.add(url)
            try:
                files.append(research.download(url, f"{work}/s{idx}_{len(files)}.{ext}"))
                break
            except Exception as e:
                print(f"[media] skip {url}: {e}")
        if len(files) == 2:
            break
    return files


def generate(topic: str, out_dir: str = "output", scenes: int = 6, use_youtube: bool = False,
             progress: Progress = lambda msg, pct: print(f"[{pct:5.1f}%] {msg}")) -> str:
    t0 = time.time()
    work = os.path.abspath(f"{out_dir}/{slug(topic)}-{int(t0)}")
    os.makedirs(work, exist_ok=True)

    progress("Researching topic on Wikipedia", 5)
    facts = research.wiki_facts(topic)

    progress(f"Writing script with {script.MODEL}", 12)
    plan = script.write_script(topic, facts, scenes)
    json.dump(plan, open(f"{work}/script.json", "w"), indent=2)

    progress("Recording voiceover", 30)
    voice_files, words, offset = [], [], 0.0
    durations = []
    for i, s in enumerate(plan["scenes"]):
        raw = f"{work}/v{i}.mp3"
        timings = voice.synthesize(s["narration"], raw)
        padded = f"v{i}.wav"
        render.ff("-i", raw, "-af", f"apad=pad_dur={render.GAP}", "-ar", "44100", "-ac", "2", padded, cwd=work)
        d = render.duration(f"{work}/{padded}")
        words += [{**w, "start": w["start"] + offset, "end": w["end"] + offset} for w in timings]
        voice_files.append(padded)
        durations.append(d)
        offset += d
    render.captions_ass(words, f"{work}/captions.ass", plan["title"])

    progress("Finding footage & images", 45)
    used: set = set()
    subject = script.subject(topic, facts["title"])
    # serial on purpose: upload.wikimedia.org rate-limits parallel clients (HTTP 429)
    credits: list[dict] = []
    media = [_gather_media(sc, i, work, used, subject, use_youtube, credits)
             for i, sc in enumerate(plan["scenes"])]
    plan["credits"] = credits

    clips, shot = [], 0
    for i, (files, d) in enumerate(zip(media, durations)):
        progress(f"Animating scene {i + 1}/{len(durations)}", 55 + 30 * i / len(durations))
        files = files or [None]
        part = d / len(files)
        for j, f in enumerate(files):
            out = f"c{i}_{j}.mp4"
            path = f"{work}/{out}"
            try:
                if f is None:
                    render.title_card(path, part)
                elif f.endswith(".mp4"):
                    render.video_clip(f, path, part)
                else:
                    render.still_clip(f, path, part, shot)
            except RuntimeError as e:  # corrupt/odd image -> title card instead of failing the run
                print(f"[render] {e}")
                render.title_card(path, part)
            clips.append(out)
            shot += 1

    progress("Mixing music, captions & final encode", 88)
    final = os.path.abspath(f"{out_dir}/{slug(plan['title'])}-{int(t0)}.mp4")
    render.assemble(work, clips, voice_files, final)
    json.dump(plan, open(final[:-4] + ".json", "w"), indent=2)  # script travels with the video
    if credits:  # CC BY requires attribution
        with open(final[:-4] + ".credits.txt", "w", encoding="utf-8") as f:
            f.writelines(f'"{c["title"]}" by {c["channel"]}, {c["url"]} ({c["license"]})\n'
                         for c in credits)
    progress(f"Done in {time.time() - t0:.0f}s", 100)
    return final
