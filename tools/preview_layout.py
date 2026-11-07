"""Composite every scene of a built collection from its JSON layout, without OBS (dev tool; Pillow + ffmpeg).

  python tools/preview_layout.py "dist/<slug>/<Name> Brand Kit.json" --out <dir> [--canvas main|vertical]

Reads positions, scales, alignment, bounds (fit / fill + crop) and visibility exactly as written for OBS,
draws media and images from the kit's assets, and labelled stand-ins for webcam, game, window and widgets.
Use it to check layouts on canvases OBS can't screenshot (the Aitum Vertical canvas).
"""
import argparse, json, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\segoeuib.ttf"
STAND_IN = {"dshow_input": ("WEBCAM", (70, 78, 92)), "game_capture": ("GAME", (44, 52, 70)),
            "window_capture": ("WINDOW / CONTENT", (52, 60, 76))}

def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except OSError:
        return ImageFont.load_default()

def load_media(path, t=2.0):
    if path.lower().endswith(".png"):
        return Image.open(path).convert("RGBA")
    with tempfile.TemporaryDirectory() as d:
        o = os.path.join(d, "f.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-c:v", "libvpx-vp9", "-ss", str(t), "-i", path,
                        "-frames:v", "1", o], check=True)
        im = Image.open(o).convert("RGBA"); im.load()
        return im

def stand_in(label, col, w=1920, h=1080):
    im = Image.new("RGBA", (w, h), col + (255,)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(140, 150, 170, 255), width=6)
    d.text((w / 2, h / 2), label, font=font(int(h * 0.09)), fill=(200, 206, 220, 255), anchor="mm")
    return im

def placeholder(label, w, h):
    im = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for x in range(0, int(w), 24):  # dashed outline
        d.line((x, 0, x + 12, 0), fill=(255, 210, 90, 230), width=4); d.line((x, h - 2, x + 12, h - 2), fill=(255, 210, 90, 230), width=4)
    for y in range(0, int(h), 24):
        d.line((0, y, 0, y + 12), fill=(255, 210, 90, 230), width=4); d.line((w - 2, y, w - 2, y + 12), fill=(255, 210, 90, 230), width=4)
    d.text((w / 2, h / 2), label, font=font(max(14, min(44, int(min(h * 0.22, w * 0.07))))), fill=(255, 220, 120, 255), anchor="mm")
    return im

class Previewer:
    def __init__(self, coll_path):
        self.root = os.path.dirname(os.path.abspath(coll_path))
        self.coll = json.load(open(coll_path, encoding="utf-8"))
        self.by_uuid = {s["uuid"]: s for s in self.coll["sources"]}
        self.cache = {}

    def canvas_size(self, scene):
        return (1080, 1920) if scene.get("canvas_uuid") else (self.coll["resolution"]["x"], self.coll["resolution"]["y"])

    def source_image(self, s, parent_size):
        k = s["id"]; st = s["settings"]
        if s["uuid"] in self.cache:
            return self.cache[s["uuid"]]
        if k in ("ffmpeg_source", "image_source"):
            p = st.get("local_file") or st.get("file")
            im = load_media(os.path.join(self.root, p[2:]))
        elif k == "browser_source":
            im = placeholder(s["name"].upper(), st["width"], st["height"])
        elif k in STAND_IN:
            im = stand_in(*STAND_IN[k])
        elif k.startswith("text"):
            f = font(st["font"]["size"]); t = st["text"]
            bb = f.getbbox(t); im = Image.new("RGBA", (bb[2] + 16, bb[3] + 16), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((8, 4), t, font=f, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(120, 20, 110, 255))
        elif k == "scene":
            im = self.render(s, parent_size)
        else:
            return None  # audio etc.
        self.cache[s["uuid"]] = im
        return im

    def render(self, scene, size=None):
        W, H = size or self.canvas_size(scene)
        out = Image.new("RGBA", (W, H), (12, 12, 14, 255) if scene.get("canvas_uuid") or size is None else (0, 0, 0, 0))
        for it in scene["settings"]["items"]:
            if not it["visible"]:
                continue
            s = self.by_uuid.get(it["source_uuid"])
            im = s and self.source_image(s, (W, H))
            if im is None:
                continue
            bw, bh = it["bounds"]["x"], it["bounds"]["y"]
            if it["bounds_type"] in (2, 3) and bw and bh:
                r = (max if it["bounds_type"] == 3 else min)(bw / im.width, bh / im.height)
                tw, th = round(im.width * r), round(im.height * r)
                im2 = im.resize((tw, th), Image.LANCZOS)
                if it["bounds_crop"]:
                    l, t = (tw - bw) / 2, (th - bh) / 2
                    im2 = im2.crop((int(l), int(t), int(l + bw), int(t + bh)))
                ox, oy = (bw - im2.width) / 2, (bh - im2.height) / 2
            else:
                tw, th = round(im.width * it["scale"]["x"]), round(im.height * it["scale"]["y"])
                if tw <= 0 or th <= 0:
                    continue
                im2 = im.resize((tw, th), Image.LANCZOS); ox = oy = 0
            x, y = it["pos"]["x"], it["pos"]["y"]
            if it["align"] == 0:  # centred on pos
                x, y = x - im2.width / 2, y - im2.height / 2
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(im2, (round(x + ox), round(y + oy)))
            out.alpha_composite(layer)
        return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("collection"); ap.add_argument("--out", required=True)
    ap.add_argument("--canvas", choices=("main", "vertical"), default="vertical")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pv = Previewer(a.collection)
    for s in pv.coll["sources"]:
        if s["id"] != "scene" or bool(s.get("canvas_uuid")) != (a.canvas == "vertical"):
            continue
        im = pv.render(s)
        p = os.path.join(a.out, "layout_" + "".join(ch if ch.isalnum() else "_" for ch in s["name"]) + ".png")
        im.convert("RGB").save(p); print(p)

if __name__ == "__main__":
    main()
