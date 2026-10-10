"""ffmpeg rendering: Ken Burns stills, stock clips, generated music, karaoke captions, final mix."""
import json
import subprocess

W, H, FPS = 1080, 1920, 30
GAP = 0.35  # breathing room after each scene's narration


def ff(*args: str, cwd: str | None = None) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(f"ffmpeg failed: {res.stderr.strip()[-800:]}")


def duration(path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def still_clip(img: str, out: str, dur: float, variant: int) -> None:
    """Slow zoom/pan over a still image (Ken Burns), alternating motion per shot."""
    frames = max(1, round(dur * FPS))
    zoom = f"1+0.15*on/{frames}" if variant % 2 == 0 else f"1.15-0.15*on/{frames}"
    pan_x = ["iw/2-(iw/zoom/2)", "(iw-iw/zoom)*on/{f}", "(iw-iw/zoom)*(1-on/{f})"][variant % 3]
    vf = (f"scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
          f"zoompan=z='{zoom}':x='{pan_x.format(f=frames)}':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={FPS},setsar=1")
    ff("-i", img, "-vf", vf, "-frames:v", str(frames), *ENC, "-an", out)


def video_clip(src: str, out: str, dur: float) -> None:
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}"
    ff("-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}", "-vf", vf, *ENC, "-an", out)


def title_card(out: str, dur: float) -> None:
    """Fallback visual when no media was found: slow-drifting dark gradient (captions carry the text)."""
    ff("-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0=0x1a1612:c1=0x3a2e22:x0=0:y0=0:x1={W}:y1={H}:speed=0.008:d={dur:.3f}:r={FPS}",
       *ENC, out)


def music(out: str, dur: float) -> None:
    """Royalty-free ambient pad synthesized on the fly (Am - F - C - G, 4s per chord)."""
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    terms = []
    for i, (a, b, c) in enumerate(chords):
        gate = f"between(mod(t,16),{i*4},{i*4+4})"
        terms.append(f"{gate}*(sin(2*PI*{a}*t)+sin(2*PI*{b}*t)+0.6*sin(2*PI*{c}*t)+0.4*sin(2*PI*{a/2}*t))")
    expr = "0.12*(" + "+".join(terms) + ")*(0.75+0.25*sin(2*PI*0.25*t))"
    ff("-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur:.2f}",
       "-af", f"lowpass=f=1400,aecho=0.8:0.7:120|240:0.35|0.2,afade=t=in:d=1.5,"
              f"afade=t=out:st={max(0, dur-2.5):.2f}:d=2.5",
       "-c:a", "aac", "-b:a", "160k", out)


def _ts(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"


def captions_ass(words: list[dict], out: str, title: str = "", chunk: int = 4) -> None:
    """Editorial captions: short phrases, sentence case, spoken word lit, the rest dimmed.
    Plus a serif title card for the opening seconds."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Segoe UI Semibold,78,&H00F4F7FA,&H00F4F7FA,&H64000000,&H96000000,0,0,0,0,100,100,0.5,0,1,0,4,2,120,120,420,1
Style: Title,Georgia,100,&H00F4F7FA,&H00FFFFFF,&H00000000,&H78000000,0,1,0,0,100,100,0,0,1,0,3,8,120,120,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if title:
        fade = r"{\fad(500,700)}"
        lines.append(f"Dialogue: 1,0:00:00.35,0:00:03.60,Title,,0,0,0,,{fade}{title}")
    groups = _phrases(words, chunk)
    for gi, group in enumerate(groups):
        # a phrase lingers briefly after its last word, but never into the next phrase (libass would stack them)
        linger = min(group[-1]["end"] + 0.15, groups[gi + 1][0]["start"]) if gi + 1 < len(groups) \
            else group[-1]["end"] + 0.15
        for j, w in enumerate(group):
            end = group[j + 1]["start"] if j + 1 < len(group) else linger
            parts = [g["text"] if k == j else r"{\c&H9AA0A6&}" + g["text"] + r"{\c&HFAF7F4&}"
                     for k, g in enumerate(group)]
            lines.append(f"Dialogue: 0,{_ts(w['start'])},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
    with open(out, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")


def _phrases(words: list[dict], size: int) -> list[list[dict]]:
    """Group words into caption phrases, breaking on pauses so lines never straddle sentences."""
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= size or w["start"] - cur[-1]["end"] > 0.25):
            out.append(cur)
            cur = []
        cur.append(w)
    return out + ([cur] if cur else [])


def shade(out: str) -> None:
    """Top/bottom darkening mask so the title and captions read on any photo."""
    alpha = (r"255*(0.78*pow(clip((Y-1000)/920\,0\,1)\,1.4)"
             r"+0.55*pow(clip((520-Y)/520\,0\,1)\,1.6))")
    ff("-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:d=1,format=rgba,geq=r=0:g=0:b=0:a='{alpha}'",
       "-frames:v", "1", out)


def assemble(work: str, clips: list[str], voice: list[str], out: str) -> None:
    """Concat scene clips + narration, mix in music, burn captions. Runs inside `work` so
    the subtitles filter gets a relative path (avoids Windows drive-letter escaping)."""
    with open(f"{work}/clips.txt", "w") as f:
        f.writelines(f"file '{c}'\n" for c in clips)
    with open(f"{work}/voice.txt", "w") as f:
        f.writelines(f"file '{v}'\n" for v in voice)
    ff("-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "video.mp4", cwd=work)
    ff("-f", "concat", "-safe", "0", "-i", "voice.txt", "-c:a", "pcm_s16le", "narration.wav", cwd=work)
    total = duration(f"{work}/narration.wav")
    music(f"{work}/music.m4a", total)
    shade(f"{work}/shade.png")
    ff("-i", "video.mp4", "-i", "narration.wav", "-i", "music.m4a", "-loop", "1", "-i", "shade.png",
       "-filter_complex",
       "[1:a]asplit=2[n1][n2];[2:a]volume=0.55[m];"
       "[m][n1]sidechaincompress=threshold=0.03:ratio=6:release=400[duck];"
       "[n2][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a];"
       # film look: gentle contrast, muted warm palette, vignette, grain, fades
       f"[0:v]eq=contrast=1.07:saturation=0.86:gamma=0.98,"
       f"colorbalance=rs=0.04:gs=0.01:bs=-0.04:rh=0.03:bh=-0.03,vignette=PI/5,"
       f"noise=alls=5:allf=t[g];[g][3:v]overlay=shortest=1,"
       f"subtitles=captions.ass,fade=t=in:d=0.6,fade=t=out:st={total-0.8:.2f}:d=0.8[v]",
       "-map", "[v]", "-map", "[a]", *ENC, "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", "-shortest", out, cwd=work)
