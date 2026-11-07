"""The brand's motion assets, built as EffectCraft comps and rendered to WebM / PNG.

Every builder takes (brand, work) and returns {"file", "w", "h"}; `work.proj(name)` is where its
editable .ecproj goes, `work.out(file)` where the rendered file goes.
Style rules: one accent, thin strokes, eased 0.3-0.6 s moves, slow loops. Nothing flashes.
"""
import os, re
from .ec import Comp, Sfx, svg, LIB, encode_webm

W, H = 1920, 1080
LOGOS = os.path.join(os.path.dirname(__file__), "logos")

# ---------------------------------------------------------------- helpers
def period(b):
    return 12.0 if b["style"]["motion"] == "calm" else 8.0

def glyph(platform, size, fill):
    d = re.search(r'<path d="([^"]+)"', open(os.path.join(LOGOS, f"{platform}.svg"), encoding="utf-8").read()).group(1)
    return svg(size, size, f'<g transform="scale({size / 24:.4f})"><path d="{d}" fill="{fill}"/></g>')

def rrect(w, h, r, fill, fill_op=1.0, stroke=None, sw=0, stroke_op=1.0):
    s = f' stroke="{stroke}" stroke-width="{sw}" stroke-opacity="{stroke_op}"' if stroke else ""
    o = sw / 2
    return svg(w, h, f'<rect x="{o}" y="{o}" width="{w - sw}" height="{h - sw}" rx="{max(0, r - o)}" '
                     f'fill="{fill}" fill-opacity="{fill_op}"{s}/>')

def logo_size(path):
    s = open(path, encoding="utf-8").read()
    m = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)', s)
    return (float(m.group(1)), float(m.group(2))) if m else (200.0, 200.0)

def add_logo(c, b, pos, size, k="1", exprs=None):
    """Brand logo centred on pos, `size` px wide. k: JS expression for a 0..1 scale factor."""
    p = b["logo_path"]
    e = dict(exprs or {})
    if not p:  # no logo: a monogram tile
        p_svg = svg(200, 200, f'<rect x="4" y="4" width="192" height="192" rx="40" fill="{b.palette["surface"]}" '
                              f'stroke="{b.palette["primary"]}" stroke-width="6"/>')
        c.shape("Logo tile", p_svg, [100, 100], pos, {**e, "transform/scale": LIB + f"var k={k};[k*{size/2},k*{size/2},100]"})
        return c.text("Logo letter", b.name[0].upper(), [pos[0], pos[1] + size * 0.17], size * 0.48,
                      b.fonts["heading"], b.palette["text"])
    if p.lower().endswith(".svg"):
        lw, lh = logo_size(p)
        sc = size / lw * 100
        e["transform/scale"] = LIB + f"var k={k};[k*{sc},k*{sc},100]"
        return c.shape("Logo", open(p, encoding="utf-8").read(), [lw / 2, lh / 2], pos, e)
    return c.image("Logo", p, pos, size, {**e, "transform/scale": f"var k={k}"})

def mix(a, b_, t):
    """Blend two hex colours (t=0 -> a, t=1 -> b_)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; cb = [int(b_[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))

def text_outline(b, size):
    """Bubble style gives free-standing text an outline so it reads on light backgrounds."""
    return {"outline": b.palette["outline"], "outline_w": max(3, size * 0.12)} if b["style"]["title"] == "bubble" else {}

def cloud_svg(w, h, fill, shade, seed, flat_bottom=True):
    """A puffy cloud: a row of overlapping circles on a rounded base, shaded towards the bottom."""
    import random
    rnd = random.Random(seed)
    body = (f'<defs><linearGradient id="c{seed}" x1="0" y1="0" x2="0" y2="1"><stop offset="0.35" stop-color="{fill}"/>'
            f'<stop offset="1" stop-color="{shade}"/></linearGradient></defs><g fill="url(#c{seed})">')
    x, base = 0.0, h * 0.62
    while x < w:
        r = rnd.uniform(0.22, 0.38) * h
        cx = min(max(x + r * 0.7, r), w - r)
        body += f'<circle cx="{cx:.1f}" cy="{base - rnd.uniform(0, 0.25) * h + r * 0.35:.1f}" r="{r:.1f}"/>'
        x += r * 1.15
    body += f'<rect x="0" y="{base:.1f}" width="{w}" height="{h - base:.1f}" rx="{(h - base) / 2 if not flat_bottom else 0:.1f}"/></g>'
    return svg(w, h, body)

def sparkle_svg(d, col):
    m = d / 2; k = d * 0.11
    return svg(d, d, f'<path d="M{m} 0 Q{m + k} {m - k} {d} {m} Q{m + k} {m + k} {m} {d} Q{m - k} {m + k} 0 {m} Q{m - k} {m - k} {m} 0Z" fill="{col}"/>')

def add_sky(c, b, P, cw=W, ch=H):
    """Pastel sky: diagonal gradient, clouds along the bottom and top corners, twinkling sparkles."""
    import random
    p = b.palette; rnd = random.Random(7)
    grad = (f'<defs><linearGradient id="sky" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{p["bg"]}"/>'
            f'<stop offset="0.55" stop-color="{mix(p["bg"], p["bg2"], 0.55)}"/><stop offset="1" stop-color="{p["bg2"]}"/>'
            f'</linearGradient></defs><rect width="{cw}" height="{ch}" fill="url(#sky)"/>')
    c.shape("Sky", svg(cw, ch, grad), [0, 0], [0, 0])
    sx, sy = cw / W, ch / H
    for layer in range(2):  # star dust, two layers fading in turn
        dots = "".join(f'<circle cx="{rnd.uniform(0, cw):.0f}" cy="{rnd.uniform(0, ch * 0.8):.0f}" r="{rnd.uniform(1.5, 4):.1f}" '
                       f'fill="#FFFFFF" fill-opacity="{rnd.uniform(0.4, 0.9):.2f}"/>' for _ in range(45))
        c.shape(f"Dust {layer}", svg(cw, ch, dots), [0, 0], [0, 0], {
            "transform/opacity": LIB + f"55+40*Math.sin(2*Math.PI*time/{P / 2}+{layer * 3.1416})"})
    for i in range(11):
        d = rnd.uniform(26, 60); x, y = rnd.uniform(60, cw - 60), rnd.uniform(40, ch * 0.75)
        n = rnd.choice((2, 3, 4)); ph = rnd.uniform(0, 6.28)
        c.shape(f"Sparkle {i}", sparkle_svg(d, "#FFFFFF"), [d / 2, d / 2], [x, y], {
            "transform/scale": LIB + f"var k=0.55+0.45*Math.abs(Math.sin(Math.PI*time*{n}/{P}+{ph:.2f}));[k*100,k*100,100]",
            "transform/opacity": LIB + f"40+60*Math.abs(Math.sin(Math.PI*time*{n}/{P}+{ph:.2f}))"})
    shade = mix(p["cloud"], p["bg2"], 0.28)
    clouds = [  # (x centre, y centre, w, h, flip)
        (180, 1000, 760, 380, False), (760, 1060, 900, 360, False), (1300, 1040, 820, 380, False),
        (1820, 980, 760, 420, False), (60, 60, 620, 360, True), (1880, 70, 640, 380, True)]
    k = min(1.0, sx * 1.4)  # narrower canvas: smaller clouds
    for i, (x, y, w, h, flip) in enumerate(clouds):
        x, w, h = x * sx, int(w * k), int(h * k)
        if not flip:  # keep bottom clouds hugging the bottom edge
            y = ch - (H - y) * k
        flipy = -100 if flip else 100
        c.shape(f"Cloud {i}", cloud_svg(w, h, p["cloud"], shade, 20 + i), [w / 2, h / 2], [x, y], {
            "transform/position": LIB + f"[{x}+16*loop(time,{P})*{1 if i % 2 else -1},{y}+5*Math.cos(2*Math.PI*time/{P}),0]",
            "transform/scale": f"[100,{flipy},100]"})

def add_bg(c, b, P, cw=W, ch=H):
    """Brand background on a seamless loop of P seconds: 'glow' (flat with two soft glows) or 'sky'."""
    if b["style"]["background"] == "sky":
        return add_sky(c, b, P, cw, ch)
    p = b.palette; sx, sy = cw / W, ch / H
    c.shape("Background", svg(cw, ch, f'<rect width="{cw}" height="{ch}" fill="{p["bg"]}"/>'), [0, 0], [0, 0])
    def glow(name, col, op, r):
        g = (f'<defs><radialGradient id="g"><stop offset="0" stop-color="{col}" stop-opacity="{op}"/>'
             f'<stop offset="1" stop-color="{col}" stop-opacity="0"/></radialGradient></defs>'
             f'<circle cx="{r}" cy="{r}" r="{r}" fill="url(#g)"/>')
        return svg(2 * r, 2 * r, g)
    c.shape("Glow 1", glow("g1", p["primary"], 0.20, 760), [760, 760], [520 * sx, 360 * sy], {
        "transform/position": LIB + f"[{520 * sx}+160*loop(time,{P}),{360 * sy}+90*Math.cos(2*Math.PI*time/{P}),0]"})
    c.shape("Glow 2", glow("g2", p["accent"], 0.07, 620), [620, 620], [1460 * sx, 820 * sy], {
        "transform/position": LIB + f"[{1460 * sx}-140*loop(time,{P}),{820 * sy}-70*Math.cos(2*Math.PI*time/{P}),0]"})

def measure(b, work, items):
    """items: [(text, font, size, style)] -> widths in px."""
    c = Comp("Measure", 2000, 200, 1, work.proj("_measure"))
    names = []
    for i, (t, font, size, style) in enumerate(items):
        n = f"m{i}"
        c.text(n, t, [100, 100], size, font, "#ffffff", style=style, justify="left")
        names.append(n)
    w = c.text_widths(names)
    return [w[n] for n in names]

def video(c, work, file, alpha, audio=None):
    tmp = c.render_video(work.out(file), alpha)
    wav = None
    if audio:
        wav = work.out(file + ".wav"); audio.write(wav)
    encode_webm(tmp, work.out(file), alpha, wav)
    if wav:
        os.remove(wav)
    return {"file": file, "w": c.w, "h": c.h}

def still(c, work, file):
    c.still(0, work.out(file), transparent=True)
    return {"file": file, "w": c.w, "h": c.h}

# ---------------------------------------------------------------- full-screen scenes
def bubble_title(c, b, work, kind, P, cw=W, ch=H):
    """Bubbly outlined title: optional kicker line, heading split over two lines, gentle breathing."""
    p = b.palette; f = b.fonts; font, st = f["heading"], f["heading_style"]
    head = b.text[kind].upper()
    words = head.split(" ")
    lines = [" ".join(words[:-1]), words[-1]] if len(words) > 1 and len(head) > 9 else [head]
    kicker = (b.text.get(f"{kind}_kicker") or "").upper()
    size = 210 if len(lines) == 2 else 190
    widths = measure(b, work, [(l, font, size, st) for l in lines] + ([(kicker, font, 92, st)] if kicker else []))
    size = size * min(1.0, cw * 0.78 / max(widths[:len(lines)]))
    ks = 92 * min(1.0, cw * 0.73 / widths[-1]) if kicker else 0
    cx = cw / 2
    top = (300 if kicker else 380) if ch <= cw else ch * 0.3
    if b["style"]["screen_logo"] and b["logo_path"]:
        add_logo(c, b, [cx, top - (130 if kicker else 70)], 120)
    if kicker:
        c.text("Kicker", kicker, [cx, top], ks, font, p["accent"], style=st, outline=p["outline"], outline_w=ks * 0.14,
               exprs={"transform/scale": LIB + f"var k=1+0.012*loop(time,{P / 2});[k*100,k*100,100]"})
    y = top + size * 0.95
    for i, line in enumerate(lines):
        e = {"transform/scale": LIB + f"var k=1+0.015*Math.sin(2*Math.PI*time/{P / 2}+{0.9 * (i + 1)});[k*100,k*100,100]"}
        c.text(f"Line {i} depth", line, [cx, y + size * 0.05], size, font, p["outline"], style=st,
               outline=p["outline"], outline_w=size * 0.12, exprs=e)
        c.text(f"Line {i}", line, [cx, y], size, font, "#FFFFFF", style=st, outline=p["outline"],
               outline_w=size * 0.1, exprs=e)
        y += size * 1.08
    sub = b.text.get(f"{kind}_sub")
    if sub:
        c.text("Sub", sub, [cx, y - size * 0.35], 44, f["body"], "#FFFFFF", **text_outline(b, 44))

def screen(kind, cw=W, ch=H, suffix=""):
    def build(b, work):
        P = period(b); p = b.palette; f = b.fonts
        name = f"screen_{kind}{suffix}"
        c = Comp(f"Screen {kind}{suffix}", cw, ch, P, work.proj(name))
        add_bg(c, b, P, cw, ch)
        if b["style"]["title"] == "bubble":
            bubble_title(c, b, work, kind, P, cw, ch)
            return video(c, work, f"{name}.webm", alpha=False)
        cx, fy = cw / 2, (lambda y: y / H * ch)  # clean layout: same proportions on any canvas
        if b["style"]["screen_logo"]:
            add_logo(c, b, [cx, fy(370)], 190, exprs={
                "transform/position": LIB + f"[{cx},{fy(370)}+6*loop(time,{P / 2}),0]"})
        hs = 92 * min(1.0, cw / W * 1.6)
        c.text("Heading", b.text[kind], [cx, fy(590)], hs, f["heading"], p["text"], style=f["heading_style"])
        if b.text.get(f"{kind}_sub"):
            c.text("Sub", b.text[f"{kind}_sub"], [cx, fy(590) + 60], 34, f["body"], p["muted"], style="Regular")
        by = fy(590) + 130
        if kind in ("starting", "brb"):  # a quiet "something is happening" bar
            c.shape("Track", rrect(320, 4, 2, p["text"], 0.12), [160, 2], [cx, by])
            c.shape("Runner", rrect(64, 4, 2, p["primary"]), [32, 2], [cx, by], {
                "transform/position": LIB + f"[{cx}+128*loop(time,{P / 4}),{by},0]"})
        else:
            c.shape("Rule", rrect(48, 4, 2, p["accent"]), [24, 2], [cx, by])
        return video(c, work, f"{name}.webm", alpha=False)
    return build

def bg_loop(cw=W, ch=H, suffix=""):
    def build(b, work):
        P = period(b)
        c = Comp(f"Background loop{suffix}", cw, ch, P, work.proj(f"bg_loop{suffix}"))
        add_bg(c, b, P, cw, ch)
        return video(c, work, f"bg_loop{suffix}.webm", alpha=False)
    return build

# ---------------------------------------------------------------- transition
STINGER_POINT_MS = 600

def stinger(cw=W, ch=H, suffix=""):
    """Brand stinger: 'panels' wipe, 'clouds' roll-in, or the brand's own file (copied as is)."""
    def build(b, work):
        t = b["transition"]
        if t.get("file"):
            import shutil
            src = os.path.join(b.dir, t["file"] if not suffix else t.get("file_vertical", t["file"]))
            name = f"stinger{suffix}" + os.path.splitext(src)[1].lower()
            shutil.copy2(src, work.out(name))
            return {"file": name, "w": cw, "h": ch, "point_ms": int(t["point_ms"])}
        if t["style"] == "clouds":
            return clouds_stinger(b, work, cw, ch, suffix)
        return panels_stinger(b, work, cw, ch, suffix)
    return build

STINGER_CLOUDS_MS = 900

def clouds_stinger(b, work, cw, ch, suffix):
    """Puffy clouds drift in, a cloud bank rises and covers the screen, then rolls off to the right."""
    import random
    p = b.palette; dur = 1.7
    fill, shade = p["cloud"], mix(p["cloud"], p["bg2"], 0.25)
    c = Comp(f"Stinger{suffix}", cw, ch, dur, work.proj(f"stinger{suffix}"))
    sx = cw / W
    for i, (x0, w) in enumerate(((260, 520), (1560, 600), (900, 420))):  # small clouds drifting up first
        x0, w = x0 * sx, w * min(1.0, sx * 1.4); h = w * 0.5
        c.shape(f"Puff {i}", cloud_svg(int(w), int(h), fill, shade, 40 + i), [w / 2, h / 2], [x0, ch + h], {
            "transform/position": LIB + f"[{x0}+{(-1) ** i * 60}*eo(time,0,0.9),{ch + h}-{ch * 0.55 + i * 90}*eio(time,{0.05 * i},0.75),0]",
            "transform/opacity": LIB + "(1-ramp(time,0.85,0.1))*100"})
    BW, BH = cw + 700, ch + 620
    def bank(seed, edge):
        body = (f'<defs><linearGradient id="b{seed}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{fill}"/>'
                f'<stop offset="1" stop-color="{shade}"/></linearGradient></defs><g fill="url(#b{seed})">')
        r2 = random.Random(seed)
        if edge == "top":
            body += f'<rect x="0" y="300" width="{BW}" height="{BH - 300}"/>'
            x = 0
            while x < BW:
                r = r2.uniform(150, 260); body += f'<circle cx="{x + r * 0.6:.0f}" cy="{300 + r2.uniform(-40, 60):.0f}" r="{r:.0f}"/>'; x += r * 1.1
        else:  # left edge bumps
            body += f'<rect x="300" y="0" width="{BW - 300}" height="{BH}"/>'
            y = 0
            while y < BH:
                r = r2.uniform(150, 260); body += f'<circle cx="{300 + r2.uniform(-40, 60):.0f}" cy="{y + r * 0.6:.0f}" r="{r:.0f}"/>'; y += r * 1.1
        return svg(BW, BH, body + "</g>")
    cut = STINGER_CLOUDS_MS / 1000
    # bank 1 rises from the bottom (bumpy top edge) and covers the canvas before the cut
    for name, seed, op, t0, d in (("Bank rising (back)", 11, 70, 0.22, 0.6), ("Bank rising", 12, 100, 0.3, 0.55)):
        c.shape(name, bank(seed, "top"), [BW / 2, 0], [cw / 2, ch + 80], {
            "transform/position": LIB + f"[{cw / 2},{ch + 80}-{ch + 420}*eio(time,{t0},{d}),0]",
            "transform/opacity": LIB + f"(time<{cut})?{op}:0"})
    # bank 2 takes over at the cut (same colour, invisible swap) and rolls off to the right
    c.shape("Bank leaving", bank(13, "left"), [0, BH / 2], [-300, ch / 2], {
        "transform/position": LIB + f"[-300+{cw + 400}*eio(time,{cut + 0.08},0.6),{ch / 2},0]",
        "transform/opacity": LIB + f"(time>={cut})?100:0"})
    sfx = Sfx(dur)
    sfx.put(0.15, sfx.whoosh(0.7, True), 0.45, -0.3)
    sfx.put(cut + 0.05, sfx.whoosh(0.6, False), 0.35, 0.5)
    out = video(c, work, f"stinger{suffix}.webm", alpha=True, audio=sfx)
    out["point_ms"] = STINGER_CLOUDS_MS
    return out

def panels_stinger(b, work, cw, ch, suffix):
    p = b.palette; dur = 1.3
    c = Comp(f"Stinger{suffix}", cw, ch, dur, work.proj(f"stinger{suffix}"))
    for name, col, t_in, t_out in (("Panel primary", p["primary"], 0.0, 0.80), ("Panel bg", p["bg"], 0.08, 0.72)):
        c.shape(name, svg(cw, ch, f'<rect width="{cw}" height="{ch}" fill="{col}"/>'), [0, 0], [0, 0], {
            "transform/position": LIB + f"[-{cw}*(1-eio(time,{t_in},0.5))+{cw}*eio(time,{t_out},0.48),0,0]"})
    add_logo(c, b, [cw / 2, ch / 2], 220, k="0.92+0.08*eo(time,0.42,0.3)", exprs={
        "transform/opacity": LIB + "(ramp(time,0.42,0.12)-ramp(time,0.70,0.1))*100"})
    sfx = Sfx(dur)
    sfx.put(0.0, sfx.whoosh(0.55, True), 0.5, -0.5)
    sfx.put(0.72, sfx.whoosh(0.5, False), 0.4, 0.5)
    return video(c, work, f"stinger{suffix}.webm", alpha=True, audio=sfx)

# ---------------------------------------------------------------- lower third
def lower_third(b, work):
    p = b.palette; f = b.fonts; dur = 7.0
    sub = b.tagline or "@" + b.handle
    wn, ws = measure(b, work, [(b.name, f["heading"], 52, f["heading_style"]), (sub, f["body"], 28, "Regular")])
    pw = max(420, int(max(wn, ws)) + 84)
    Wl, Hl = pw + 60, 170
    c = Comp("Lower third", Wl, Hl, dur, work.proj("lower_third"))
    out = "(1-eio(time,5.9,0.45))"
    c.shape("Panel", rrect(pw, 112, b["style"]["radius"], p["surface"], 0.94, "#ffffff", 1.5, 0.08), [0, 56], [30, 85], {
        "transform/scale": LIB + f"[eo(time,0.15,0.5)*{out}*100,100,100]"})
    c.shape("Accent", rrect(6, 112, 3, p["primary"]), [3, 56], [30, 85], {
        "transform/scale": LIB + f"[100,eo(time,0,0.35)*(1-eio(time,6.3,0.3))*100,100]"})
    for name, text, y, size, font, col, style, t0 in (
            ("Name", b.name, 80, 52, f["heading"], p["text"], f["heading_style"], 0.45),
            ("Tagline", sub, 122, 28, f["body"], p["muted"], "Regular", 0.6)):
        c.text(name, text, [64, y], size, font, col, style=style, justify="left", exprs={
            "transform/opacity": LIB + f"(ramp(time,{t0},0.25)-ramp(time,5.7,0.2))*100",
            "transform/position": LIB + f"[64-18*(1-eo(time,{t0},0.45)),{y},0]"})
    return video(c, work, "lower_third.webm", alpha=True)

# ---------------------------------------------------------------- socials
def socials_rotator(b, work):
    """One social at a time: icon pops, handle slides out of it, then hands over to the next."""
    p = b.palette; f = b.fonts
    S = 4.0 if b["style"]["motion"] == "calm" else 3.0
    socials = b.socials; n = len(socials)
    widths = measure(b, work, [(s["handle"], f["body"], 30, "Medium") for s in socials])
    Wr, Hr, D = 40 + 72 + int(max(widths)) + 60, 96, 72
    c = Comp("Socials rotator", Wr, Hr, n * S, work.proj("socials_rotator"))
    for k, (s, tw) in enumerate(zip(socials, widths)):
        t0, t1 = k * S, (k + 1) * S
        on = f"(time>={t0}&&time<{t1})?100:0"
        pill_w = D / 2 + 20 + tw + 30
        c.shape(f"{k} pill", rrect(pill_w, 60, 30, p["surface"], 0.92, "#ffffff", 1.5, 0.08), [0, 30], [48, 48], {
            "transform/scale": LIB + f"[eo(time,{t0 + 0.15},0.45)*(1-eio(time,{t1 - 0.6},0.4))*100,100,100]",
            "transform/opacity": on})
        c.text(f"{k} handle", s["handle"], [48 + D / 2 + 16, 59], 30, f["body"], p["text"], style="Medium",
               justify="left", exprs={
                   "transform/opacity": LIB + f"(ramp(time,{t0 + 0.4},0.25)-ramp(time,{t1 - 0.75},0.2))*100",
                   "transform/position": LIB + f"[{48 + D / 2 + 16}-14*(1-eo(time,{t0 + 0.4},0.4)),59,0]"})
        k_icon = f"eo(time,{t0},0.35)*(1-eio(time,{t1 - 0.3},0.28))"
        c.shape(f"{k} circle", svg(D, D, f'<circle cx="{D/2}" cy="{D/2}" r="{D/2 - 1.5}" fill="{p["surface"]}" '
                                         f'stroke="{p["primary"]}" stroke-width="3"/>'), [D / 2, D / 2], [48, 48], {
            "transform/scale": LIB + f"var k={k_icon};[k*100,k*100,100]", "transform/opacity": on})
        c.shape(f"{k} {s['platform']}", glyph(s["platform"], 32, p["text"]), [16, 16], [48, 48], {
            "transform/scale": LIB + f"var k={k_icon};[k*100,k*100,100]", "transform/opacity": on})
    return video(c, work, "socials_rotator.webm", alpha=True)

def socials_row(b, work):
    """All socials in one centred row (for Starting / BRB / Ending)."""
    p = b.palette; f = b.fonts
    widths = measure(b, work, [(s["handle"], f["body"], 28, "Medium") for s in b.socials])
    D, GAP, SEP = 48, 14, 48
    total = sum(D + GAP + w for w in widths) + SEP * (len(widths) - 1)
    Wr, Hr = int(total) + 40, 72
    c = Comp("Socials row", Wr, Hr, 1, work.proj("socials_row"))
    pill = b["style"]["background"] == "sky"  # light, busy backgrounds: put the row on a soft pill
    if pill:
        c.shape("Backing", rrect(Wr, Hr, Hr / 2, p["surface"], 0.85, "#FFFFFF", 2, 0.5), [0, 0], [0, 0])
    x = 20
    for s, w in zip(b.socials, widths):
        c.shape(f"{s['platform']} circle", svg(D, D, f'<circle cx="{D/2}" cy="{D/2}" r="{D/2 - 1}" fill="{p["surface"]}" '
                                                    f'stroke="{p["primary"]}" stroke-width="2"/>'), [D / 2, D / 2], [x + D / 2, 36])
        c.shape(s["platform"], glyph(s["platform"], 22, p["text"]), [11, 11], [x + D / 2, 36])
        c.text(f"{s['platform']} handle", s["handle"], [x + D + GAP, 46], 28, f["body"], p["text"], style="Medium",
               justify="left", **({} if pill else text_outline(b, 28)))
        x += D + GAP + w + SEP
    return still(c, work, "socials_row.png")

def socials_col(b, work):
    """All socials stacked and centred (vertical canvas: Starting / BRB / Ending)."""
    p = b.palette; f = b.fonts
    widths = measure(b, work, [(s["handle"], f["body"], 34, "Medium") for s in b.socials])
    D, GAP, ROW = 56, 18, 76
    Wc = int(D + GAP + max(widths) + 72); Hc = ROW * len(b.socials) + 24
    c = Comp("Socials column", Wc, Hc, 1, work.proj("socials_col"))
    pill = b["style"]["background"] == "sky"
    if pill:
        c.shape("Backing", rrect(Wc, Hc, 36, p["surface"], 0.85, "#FFFFFF", 2, 0.5), [0, 0], [0, 0])
    for i, s in enumerate(b.socials):
        y = 12 + ROW * i + ROW / 2
        c.shape(f"{s['platform']} circle", svg(D, D, f'<circle cx="{D/2}" cy="{D/2}" r="{D/2 - 1}" fill="{p["surface"]}" '
                                                    f'stroke="{p["primary"]}" stroke-width="2"/>'), [D / 2, D / 2], [36 + D / 2, y])
        c.shape(s["platform"], glyph(s["platform"], 26, p["text"]), [13, 13], [36 + D / 2, y])
        c.text(f"{s['platform']} handle", s["handle"], [36 + D + GAP, y + 12], 34, f["body"], p["text"], style="Medium",
               justify="left", **({} if pill else text_outline(b, 34)))
    return still(c, work, "socials_col.png")

# ---------------------------------------------------------------- frames and panels (static PNG)
def cam_frame(size_name, iw, ih):
    """Frame drawn around a webcam of iw x ih. The camera sits at (stroke, stroke) inside the PNG.
    The corner radius is capped so the square camera corners never poke out of the stroke."""
    def build(b, work):
        p = b.palette; s = b["style"]["stroke"]; f = b.fonts
        r = min(b["style"]["radius"], 2.4 * s)
        g = 18 if b["style"]["frame_glow"] else 0   # room for the soft glow around the frame
        tab_h = 34 if size_name == "sm" else 40
        fw, fh = iw + 2 * s + 2 * g, ih + 2 * s + 2 * g + max(0, tab_h // 2 - g)
        c = Comp(f"Cam frame {size_name}", int(fw), int(fh), 1, work.proj(f"cam_frame_{size_name}"))
        line = lambda width, col, op: (f'<rect x="{g + s / 2}" y="{g + s / 2}" width="{iw + s}" height="{ih + s}" rx="{r + s / 2}" '
                                       f'fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{width}"/>')
        body = ""
        if g:
            body += line(s + 34, p["primary"], 0.06) + line(s + 22, p["primary"], 0.10) + line(s + 10, p["primary"], 0.18)
        body += line(s, p["primary"], 1)
        if g:  # thin light inner edge, like a candy rim
            body += (f'<rect x="{g + s - 1}" y="{g + s - 1}" width="{iw + 2}" height="{ih + 2}" rx="{r}" fill="none" '
                     f'stroke="#FFFFFF" stroke-opacity="0.75" stroke-width="2"/>')
        c.shape("Frame", svg(int(fw), int(fh), body), [0, 0], [0, 0])
        size = 18 if size_name == "sm" else 22
        (tw,) = measure(b, work, [("@" + b.handle, f["body"], size, "Medium")])
        tab_w = tw + 32
        ty = g + ih + 2 * s - tab_h / 2
        c.shape("Tab", rrect(tab_w, tab_h, tab_h / 2, p["surface"], 1, p["primary"], 1.5), [0, 0], [g + s + 14, ty])
        c.text("Handle", "@" + b.handle, [g + s + 14 + 16, ty + tab_h / 2 + size * 0.36], size, f["body"], p["text"],
               style="Medium", justify="left")
        out = still(c, work, f"cam_frame_{size_name}.png")
        out["inset"] = g + s
        return out
    return build

def chat_panel(b, work):
    p = b.palette; f = b.fonts; Wc, Hc = 480, 720
    c = Comp("Chat panel", Wc, Hc, 1, work.proj("chat_panel"))
    c.shape("Panel", rrect(Wc, Hc, b["style"]["radius"], p["surface"], 0.9, "#ffffff", 1.5, 0.08), [0, 0], [0, 0])
    c.shape("Dot", svg(10, 10, f'<circle cx="5" cy="5" r="5" fill="{p["accent"]}"/>'), [5, 5], [30, 40])
    c.text("Header", "CHAT", [46, 48], 22, f["body"], p["muted"], justify="left", tracking=120)
    c.shape("Rule", svg(Wc - 40, 2, f'<rect width="{Wc - 40}" height="1.5" fill="#ffffff" fill-opacity="0.08"/>'), [0, 0], [20, 70])
    return still(c, work, "chat_panel.png")

def label(b, work):
    """'Latest' pill for the gameplay scene; the event-list widget sits on its right part."""
    p = b.palette; f = b.fonts; Wl, Hl = 420, 56
    c = Comp("Label", Wl, Hl, 1, work.proj("label"))
    c.shape("Pill", rrect(Wl, Hl, Hl / 2, p["surface"], 0.92, "#ffffff", 1.5, 0.08), [0, 0], [0, 0])
    c.shape("Accent", rrect(4, 24, 2, p["primary"]), [2, 12], [22, 28])
    c.text("Text", "LATEST", [34, 35], 18, f["body"], p["muted"], justify="left", tracking=100)
    return still(c, work, "label.png")

def brand_tag(b, work):
    p = b.palette; f = b.fonts
    (tw,) = measure(b, work, [(b.name, f["heading"], 30, f["heading_style"])])
    Wt, Ht = int(56 + 14 + tw + 8), 64
    c = Comp("Brand tag", Wt, Ht, 1, work.proj("brand_tag"))
    add_logo(c, b, [28, 32], 56)
    c.text("Name", b.name, [56 + 14, 43], 30, f["heading"], p["text"], style=f["heading_style"], justify="left",
           **text_outline(b, 30))
    return still(c, work, "brand_tag.png")

VW, VH = 1080, 1920  # vertical canvas (Aitum Vertical default, as in the reference collection)

ASSETS = {
    "screen_starting": screen("starting"),
    "screen_brb": screen("brb"),
    "screen_ending": screen("ending"),
    "bg_loop": bg_loop(),
    "stinger": stinger(),
    "lower_third": lower_third,
    "socials_rotator": socials_rotator,
    "socials_row": socials_row,
    "cam_frame_lg": cam_frame("lg", 1280, 720),
    "cam_frame_sm": cam_frame("sm", 384, 216),
    "chat_panel": chat_panel,
    "label": label,
    "brand_tag": brand_tag,
    # vertical canvas; built only when brand.vertical is on
    "screen_starting_v": screen("starting", VW, VH, "_v"),
    "screen_brb_v": screen("brb", VW, VH, "_v"),
    "screen_ending_v": screen("ending", VW, VH, "_v"),
    "bg_loop_v": bg_loop(VW, VH, "_v"),
    "stinger_v": stinger(VW, VH, "_v"),
    "socials_col": socials_col,
}
VERTICAL_ASSETS = {k for k in ASSETS if k.endswith("_v") or k == "socials_col"}
