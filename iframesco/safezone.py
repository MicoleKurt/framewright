"""`iframesco safezone IMAGE`: check text placement on a photo before rendering.

Burns sample captions and a title card onto the photo exactly as a Short would, then draws the
Shorts UI zones (top bar, bottom handle/title/description, right-hand buttons) over the result.
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import formats, render

SAMPLE = "Before she wrote the first program Ada was a girl who dreamed of flying machines".split()


def preview(image: str, out: str, title: str = "Sample title", brand: str = "Your channel") -> str:
    fmt = formats.get("short")
    render.use(fmt)
    work = tempfile.mkdtemp(prefix="fs-safezone-")
    photo = ImageOps.fit(Image.open(image).convert("RGB"), (fmt.w, fmt.h), centering=(0.5, 0.5))
    photo.save(os.path.join(work, "photo.jpg"))
    words, t = [], 0.0
    for w in SAMPLE:
        words.append({"text": w, "start": t, "end": t + 0.32})
        t += 0.36
    render.captions_ass(words, os.path.join(work, "cap.ass"), title, brand={"name": brand, "tagline": ""})
    render.shade(os.path.join(work, "shade.png"))
    # t=1.3 s: title card and the first caption phrase are both on screen
    render.ff("-loop", "1", "-t", "2", "-i", "photo.jpg", "-loop", "1", "-t", "2", "-i", "shade.png",
              "-filter_complex", "[0:v][1:v]overlay,subtitles=cap.ass[v]", "-map", "[v]", "-ss", "1.3",
              "-frames:v", "1", "frame.png", cwd=work)
    im = Image.open(os.path.join(work, "frame.png")).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    red = (255, 60, 60)
    d.rectangle((0, 0, fmt.w, fmt.safe_top), fill=(*red, 70))
    d.rectangle((0, fmt.h - fmt.safe_bottom, fmt.w, fmt.h), fill=(*red, 80))
    d.rectangle((fmt.w - fmt.safe_right, fmt.safe_top, fmt.w, fmt.h - fmt.safe_bottom), fill=(*red, 45))
    font = ImageFont.load_default(28)
    d.text((20, fmt.h - fmt.safe_bottom + 12), "Shorts UI: handle, title, description", font=font, fill=(255, 255, 255, 230))
    Image.alpha_composite(im, ov).convert("RGB").save(out, quality=92)
    return out
