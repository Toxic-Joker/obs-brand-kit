"""Load and validate brands/<slug>/brand.json."""
import json, os, re, sys

LOGOS = os.path.join(os.path.dirname(__file__), "logos")
PLATFORMS = sorted(f[:-4] for f in os.listdir(LOGOS) if f.endswith(".svg"))
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
PALETTE_KEYS = ("bg", "surface", "primary", "accent", "text", "muted")

class Brand(dict):
    __getattr__ = dict.__getitem__

def fail(msg):
    sys.exit(f"brand.json: {msg}")

def load(folder):
    folder = os.path.abspath(folder)
    path = os.path.join(folder, "brand.json")
    if not os.path.exists(path):
        fail(f"not found in {folder}")
    b = Brand(json.load(open(path, encoding="utf-8")))
    b["dir"] = folder
    b["slug"] = os.path.basename(folder)
    for k in ("name", "handle", "palette", "fonts", "socials"):
        if k not in b:
            fail(f"missing '{k}'")
    for k in PALETTE_KEYS:
        v = b.palette.get(k)
        if not (isinstance(v, str) and HEX.match(v)):
            fail(f"palette.{k} must be a hex colour like #1A2B3C (got {v!r})")
    for s in b.socials:
        if s.get("platform") not in PLATFORMS:
            fail(f"social platform {s.get('platform')!r} unknown; use one of {PLATFORMS} "
                 f"(add an SVG to kit/logos for more)")
        if not s.get("handle"):
            fail(f"social {s['platform']} needs a handle")
    if len(b.socials) > 6:
        fail("keep it to 6 socials or fewer (they share one row)")
    for k in ("bg2", "outline", "cloud"):
        v = b.palette.get(k)
        if v is not None and not (isinstance(v, str) and HEX.match(v)):
            fail(f"palette.{k} must be a hex colour")
    b.palette.setdefault("bg2", b.palette["bg"])
    b.palette.setdefault("outline", b.palette["primary"])
    b.palette.setdefault("cloud", "#FFFFFF")
    b.setdefault("tagline", "")
    b.setdefault("style", {})
    b["style"] = {"radius": 14, "stroke": 3, "motion": "calm", "background": "glow", "title": "clean",
                  "frame_glow": False, "screen_logo": True, **b["style"]}
    for key, ok in (("motion", ("calm", "lively")), ("background", ("glow", "sky")), ("title", ("clean", "bubble"))):
        if b["style"][key] not in ok:
            fail(f"style.{key} must be one of {ok}")
    b["layout"] = {"just_chatting": "framed", "chat": "panel", "chat_on_screens": False, **b.get("layout", {})}
    for key, ok in (("just_chatting", ("framed", "fullcam")), ("chat", ("panel", "floating"))):
        if b["layout"][key] not in ok:
            fail(f"layout.{key} must be one of {ok}")
    b.setdefault("vertical", True)  # 1080x1920 scenes for the Aitum Vertical canvas (hidden when it isn't installed)
    t = b["transition"] = {"style": "panels", **b.get("transition", {})}
    if t.get("file"):
        if not os.path.exists(os.path.join(folder, t["file"])):
            fail(f"transition.file {t['file']} not found next to brand.json")
        if "point_ms" not in t:
            fail("transition.file needs point_ms (when the stinger fully covers the screen)")
    elif t["style"] not in ("panels", "clouds"):
        fail("transition.style must be 'panels' or 'clouds' (or give transition.file)")
    b.setdefault("text", {})
    b["text"] = {"starting": "Starting soon", "starting_sub": b["tagline"] or "@" + b["handle"],
                 "brb": "Be right back", "brb_sub": "Back in a moment",
                 "ending": "Thanks for watching", "ending_sub": "See you next stream", **b["text"]}
    logo = b.get("logo")
    if logo:
        lp = os.path.join(folder, logo)
        if not os.path.exists(lp):
            fail(f"logo file {logo} not found next to brand.json")
        if not lp.lower().endswith((".svg", ".png")):
            fail("logo must be .svg or .png")
        b["logo_path"] = lp
    else:
        b["logo_path"] = None
    b.fonts.setdefault("files", [])
    b.fonts.setdefault("heading_style", "Bold")
    for f in b.fonts["files"]:
        if not os.path.exists(os.path.join(folder, f)):
            fail(f"font file {f} not found")
    return b

def check_fonts(b, available):
    """EffectCraft must have the fonts to bake text into the assets."""
    for role in ("heading", "body"):
        fam = b.fonts.get(role)
        if fam not in available:
            fail(f"font '{fam}' ({role}) is not installed. Install it for Windows (right-click the "
                 f".ttf > Install for all users), or pick a bundled one: Inter, Noto Serif, JetBrains Mono.")

def obs_color(hex_, alpha=255):
    """OBS stores colours as ABGR integers."""
    r, g, b = int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16)
    return (alpha << 24) | (b << 16) | (g << 8) | r
