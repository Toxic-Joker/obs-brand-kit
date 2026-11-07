"""Build the README visuals from real build output (dev tool; needs Pillow and ffmpeg).

  python tools/readme_images.py [--obs-shots <slug>=<verify_obs out dir> ...]

Writes docs/images/: hero.png, parts_<slug>.png, stinger_<slug>.gif, screens_<slug>.gif and, when
verify_obs.py screenshots are given, scenes_<slug>.png (what OBS itself rendered).
"""
import argparse, glob, json, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "images")
BG = (24, 26, 32)
FONT = r"C:\Windows\Fonts\segoeuib.ttf"

def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except OSError:
        return ImageFont.load_default()

def frame(webm, t, w=None):
    """One frame (alpha kept via the vp9 decoder), optionally scaled to width w."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-c:v", "libvpx-vp9", "-ss", str(t), "-i", webm,
                        "-frames:v", "1", p], check=True)
        im = Image.open(p).convert("RGBA"); im.load()
    if w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    return im

def rounded(im, r=18):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.paste(im, (0, 0), mask); return out

def label(draw, xy, text, size=26, fill=(235, 237, 242)):
    draw.text(xy, text, font=font(size), fill=fill)

def brand(slug):
    b = json.load(open(os.path.join(ROOT, "brands", slug, "brand.json"), encoding="utf-8"))
    return b, os.path.join(ROOT, "dist", slug, "assets")

def hero(slugs):
    W, cw = 1830, 860
    ch = round(cw * 9 / 16)
    im = Image.new("RGBA", (W, ch + 150), BG); d = ImageDraw.Draw(im)
    for i, slug in enumerate(slugs):
        b, a = brand(slug)
        x = 30 + i * (cw + 50)
        im.alpha_composite(rounded(frame(os.path.join(a, "screen_starting.webm"), 2, cw).convert("RGBA")), (x, 30))
        st = b["style"]
        label(d, (x, ch + 50), f"{b['name']}", 34)
        label(d, (x, ch + 98), f"background: {st.get('background', 'glow')}  ·  title: {st.get('title', 'clean')}  ·  "
                                f"transition: {b.get('transition', {}).get('style', 'panels')}", 22, (150, 156, 170))
    im.convert("RGB").save(os.path.join(OUT, "hero.png"), optimize=True)

def parts(slug):
    b, a = brand(slug)
    p = b["palette"]
    bgc = tuple(int(p["bg"][i:i + 2], 16) for i in (1, 3, 5))
    items = [("Webcam frame", Image.open(os.path.join(a, "cam_frame_sm.png")).convert("RGBA")),
             ("Lower third", frame(os.path.join(a, "lower_third.webm"), 2.5)),
             ("Socials rotator", frame(os.path.join(a, "socials_rotator.webm"), 1.5)),
             ("Socials row", Image.open(os.path.join(a, "socials_row.png")).convert("RGBA")),
             ("Brand tag", Image.open(os.path.join(a, "brand_tag.png")).convert("RGBA"))]
    W = 1800; pad = 30
    bg = frame(os.path.join(a, "bg_loop.webm"), 1, W).convert("RGBA")
    # lay out in rows
    rows, row, x = [], [], pad
    for name, it in items:
        s = min(1.0, (W - 2 * pad) / it.width)
        it = it.resize((round(it.width * s), round(it.height * s)), Image.LANCZOS)
        if row and x + it.width > W - pad:
            rows.append(row); row, x = [], pad
        row.append((name, it, x)); x += it.width + 60
    rows.append(row)
    H = pad + sum(max(i.height for _, i, _ in r) + 70 for r in rows)
    im = Image.new("RGBA", (W, H), bgc + (255,))
    im.alpha_composite(bg.resize((W, H)) if bg.height < H else bg.crop((0, 0, W, H)))
    d = ImageDraw.Draw(im); y = pad
    for r in rows:
        rh = max(i.height for _, i, _ in r)
        for name, it, x in r:
            im.alpha_composite(it, (x, y + 34))
            d.text((x, y), name, font=font(24), fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 160))
        y += rh + 70
    im.convert("RGB").save(os.path.join(OUT, f"parts_{slug}.png"), optimize=True)

def gif(src_frames, out, ms):
    """Encode with ffmpeg's two-pass palette (Pillow's frame-delta GIFs leave ghosts of earlier frames)."""
    with tempfile.TemporaryDirectory() as d:
        for i, f in enumerate(src_frames):
            f.convert("RGB").save(os.path.join(d, f"{i:04d}.png"))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", f"{1000 / ms:.3f}", "-i", os.path.join(d, "%04d.png"),
                        "-vf", "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a",
                        "-loop", "0", out], check=True)

def stinger(slug, w=640, fps=15):
    """The stinger over two stand-in scenes, so the hand-over is visible."""
    b, a = brand(slug)
    s = [f for f in glob.glob(os.path.join(a, "stinger.*"))][0]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", s],
                               capture_output=True, text=True).stdout)
    before = frame(os.path.join(a, "screen_starting.webm"), 1, w).convert("RGBA")
    after = frame(os.path.join(a, "screen_brb.webm"), 1, w).convert("RGBA")
    point = json.load(open(os.path.join(ROOT, "dist", slug, "assets.json")))["stinger"].get("point_ms", 600) / 1000
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-c:v", "libvpx-vp9", "-i", s, "-vf", f"fps={fps},scale={w}:-1",
                        os.path.join(d, "%04d.png")], check=True)
        frames = []
        for i, f in enumerate(sorted(glob.glob(os.path.join(d, "*.png")))):
            base = (before if i / fps < point else after).copy()
            base.alpha_composite(Image.open(f).convert("RGBA")); frames.append(base)
    hold = [before] * 6 + frames + [after] * 10
    gif(hold, os.path.join(OUT, f"stinger_{slug}.gif"), round(1000 / fps))

def screens(slug, w=640):
    """Starting -> BRB -> Ending, a few frames each, to show the loops move."""
    b, a = brand(slug)
    frames = []
    for kind in ("starting", "brb", "ending"):
        for t in (0.0, 0.8, 1.6, 2.4, 3.2, 4.0):
            frames.append(frame(os.path.join(a, f"screen_{kind}.webm"), t, w))
    gif(frames, os.path.join(OUT, f"screens_{slug}.gif"), 220)

def scenes(slug, shots):
    names = ["Starting_Soon", "Just_Chatting", "Gameplay", "React", "Be_Right_Back", "Ending"]
    ims = [Image.open(os.path.join(shots, f"scene_{n}.png")).convert("RGB") for n in names]
    w, h = 600, 338; pad = 16
    im = Image.new("RGB", (w * 3 + pad * 4, (h + 46) * 2 + pad * 2), BG); d = ImageDraw.Draw(im)
    for i, (n, s) in enumerate(zip(names, ims)):
        x = pad + (i % 3) * (w + pad); y = pad + (i // 3) * (h + 46 + pad)
        im.paste(rounded(s.resize((w, h), Image.LANCZOS).convert("RGBA"), 10), (x, y + 40), rounded(s.resize((w, h)).convert("RGBA"), 10))
        d.text((x, y + 4), n.replace("_", " "), font=font(24), fill=(235, 237, 242))
    im.save(os.path.join(OUT, f"scenes_{slug}.png"), optimize=True)

def vertical(slug, shots=None):
    """The vertical (Aitum) scenes: OBS's own renders from verify_obs.py when given, else composited
    from the collection layout by preview_layout.py."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from preview_layout import Previewer
    b, _ = brand(slug)
    path = os.path.join(ROOT, "dist", slug, f"{b['name']} Brand Kit.json")
    pv = Previewer(path)
    vs = [s for s in pv.coll["sources"] if s.get("canvas_uuid")]
    if not vs:
        return
    w, h, pad = 300, 533, 14
    im = Image.new("RGB", (len(vs) * (w + pad) + pad, h + 60), BG); d = ImageDraw.Draw(im)
    for i, s in enumerate(vs):
        x = pad + i * (w + pad)
        shot = shots and os.path.join(shots, "vscene_" + s["name"].replace(" ", "_").replace("(", "").replace(")", "") + ".png")
        src = Image.open(shot).convert("RGBA") if shot and os.path.exists(shot) else None
        if src is None or sum(src.convert("L").resize((32, 32)).getdata()) / 1024 < 8:
            src = pv.render(s)  # nothing picked yet (webcam / game): show the layout with labelled stand-ins
        tile = rounded(src.resize((w, h), Image.LANCZOS), 12)
        im.paste(tile, (x, 46), tile)
        d.text((x, 8), s["name"].replace(" (V)", ""), font=font(22), fill=(235, 237, 242))
    im.save(os.path.join(OUT, f"vertical_{slug}.png"), optimize=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--obs-shots", nargs="*", default=[])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    slugs = sorted(os.listdir(os.path.join(ROOT, "brands")))
    hero(slugs)
    for slug in slugs:
        parts(slug); stinger(slug); screens(slug)
        print("done", slug)
    shots = dict(pair.split("=", 1) for pair in a.obs_shots)
    for slug in slugs:
        vertical(slug, shots.get(slug))
    for slug, d in shots.items():
        scenes(slug, d)
    for f in sorted(os.listdir(OUT)):
        print(f"  {f:<28} {os.path.getsize(os.path.join(OUT, f)) // 1024} KB")

if __name__ == "__main__":
    main()
