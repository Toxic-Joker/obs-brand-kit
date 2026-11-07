"""Safety and integrity checks on a built kit. Any problem -> list of messages."""
import json, os, re, zipfile

URL = re.compile(r"https?://", re.I)
# 20+ chars mixing letters and digits, outside UUIDs (keys, stream tokens, widget ids)
TOKENISH = re.compile(r"(?<![0-9a-f-])(?=[A-Za-z0-9_]*\d)(?=[A-Za-z0-9_]*[A-Za-z])[A-Za-z0-9_]{20,}(?![0-9a-f-])")
TOKENISH_OK = re.compile(r"PASTE_YOUR_[A-Z_]+_URL")
LOCAL_PATH =re.compile(r"[A-Za-z]:[\\/]|\\Users\\|/Users/|AppData", re.I)

def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj

def scan_secrets(obj, where, extra_forbidden=()):
    bad = []
    for path, s in _strings(obj):
        if URL.search(s):
            bad.append(f"{where}{path}: web URL {s[:60]!r}")
        if LOCAL_PATH.search(s):
            bad.append(f"{where}{path}: local path {s[:60]!r}")
        if TOKENISH.search(TOKENISH_OK.sub("", s)) and not path.endswith("css"):
            bad.append(f"{where}{path}: token-like string {s[:60]!r}")
        for f in extra_forbidden:
            if f and f.lower() in s.lower():
                bad.append(f"{where}{path}: contains forbidden value")
    return bad

def check_obs(coll, root_dir, extra_forbidden=()):
    bad = scan_secrets(coll, "obs", extra_forbidden)
    names = {s["name"] for s in coll["sources"]}
    for path, s in _strings(coll):
        if s.startswith("./"):
            if ".." in s or not os.path.exists(os.path.join(root_dir, s[2:])):
                bad.append(f"obs{path}: missing file {s}")
    for s in coll["sources"]:
        if s["id"] == "browser_source" and not s["settings"]["url"].startswith("about:blank#PASTE_YOUR_"):
            bad.append(f"browser source {s['name']} is not a placeholder")
        if s["id"] in ("ffmpeg_source", "image_source"):
            v = s["settings"].get("local_file") or s["settings"].get("file")
            if not v.startswith("./assets/"):
                bad.append(f"{s['name']}: path is not relative: {v}")
        if s["id"] == "scene":
            for it in s["settings"]["items"]:
                if it["name"] not in names:
                    bad.append(f"scene {s['name']}: item {it['name']} has no source")
    for sc in coll["scene_order"]:
        if sc["name"] not in names:
            bad.append(f"scene_order: {sc['name']} missing")
    return bad

def check_overlay(path, extra_forbidden=()):
    bad = []
    with zipfile.ZipFile(path) as z:
        files = set(z.namelist())
        cfg = json.loads(z.read("config.json"))
    bad += scan_secrets(cfg, "overlay", extra_forbidden)
    for p, s in _strings(cfg):
        if p.endswith(".filename") or p.endswith(".path"):
            if s not in files:
                bad.append(f"overlay{p}: {s} not in zip")
        if p.endswith(".url") and s:
            bad.append(f"overlay{p}: widget URL must be empty")
    return bad
