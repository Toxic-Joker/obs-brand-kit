"""Read-only inventory of OBS scene collections. Never writes anything; URLs are printed masked.

  python tools/obs_inventory.py list                      collections in OBS, which one is active, what kind each is
  python tools/obs_inventory.py tools  "<collection>"     tools/devices that are USED (visible in >=1 scene), per scene
  python tools/obs_inventory.py slots  "<kit .json>"      a kit collection's scenes, items, positions and sizes

<collection> = a collection name or a path to its .json.
"""
import configparser, json, os, re, sys

APPDATA = os.environ["APPDATA"]
SCENES = os.path.join(APPDATA, "obs-studio", "basic", "scenes")
MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"  # libobs' main canvas uuid
GLOBAL_AUDIO = ["DesktopAudioDevice1", "DesktopAudioDevice2", "AuxAudioDevice1", "AuxAudioDevice2",
                "AuxAudioDevice3", "AuxAudioDevice4"]
REGISTRY = os.path.join(APPDATA, "obs-studio", "obs-connect-tools.json")  # collections connect.py made

def made_by_us():
    try: return set(json.load(open(REGISTRY, encoding="utf-8")))
    except Exception: return set()

def mask(s):
    if not isinstance(s, str): return s
    return re.sub(r"[A-Za-z0-9_\-]{12,}", lambda m: m.group(0)[:3] + "..." if not re.fullmatch(r"[a-z\-]+", m.group(0)) else m.group(0), s)[:120]

def load(arg):
    p = arg if arg.lower().endswith(".json") and os.path.exists(arg) else None
    if not p:
        for f in os.listdir(SCENES):
            if f.endswith(".json"):
                try: n = json.load(open(os.path.join(SCENES, f), encoding="utf-8")).get("name")
                except Exception: continue
                if n == arg: p = os.path.join(SCENES, f); break
    if not p: sys.exit(f"no collection named {arg!r}; run `inventory.py list`")
    return p, json.load(open(p, encoding="utf-8"))

def kind_of(d):
    if d.get("name") in made_by_us(): return "personal (made by obs-connect-tools)"
    if "Brand Kit" in d.get("name", ""): return "brand kit build"
    srcs = d.get("sources", [])
    real = [s for s in srcs if s["id"] == "dshow_input" and s["settings"].get("video_device_id")] + \
           [s for s in srcs if s["id"] == "browser_source" and s["settings"].get("url", "").startswith("http")]
    scenes = sum(1 for s in srcs if s["id"] == "scene")
    if not scenes: return "empty"
    return "user collection (has real devices/widgets)" if real else "user collection (no devices/widgets)"

def cmd_list():
    ini = configparser.ConfigParser(strict=False, interpolation=None)
    ini.read(os.path.join(APPDATA, "obs-studio", "user.ini"), encoding="utf-8-sig")
    active = ini["Basic"].get("SceneCollection", "") if "Basic" in ini else ""
    rows = []
    for f in sorted(os.listdir(SCENES)):
        if not f.endswith(".json"): continue
        try: d = json.load(open(os.path.join(SCENES, f), encoding="utf-8"))
        except Exception: continue
        rows.append((d.get("name", f), f, kind_of(d)))
    if not rows: print("No scene collections in", SCENES); return
    for n, f, k in rows:
        print(f"{'*' if n == active else ' '} {n}  [{f}]  -> {k}")
    print("* = active in OBS")

def classify(s):
    i, st = s["id"], s["settings"]
    if i == "browser_source":
        u = (st.get("url", "") + " " + s["name"]).lower()
        for key, words in [("alerts", ["alert-box", "alertbox", "alert box", "/alerts"]),
                           ("multichat", ["multichat", "multi-chat"]), ("chat", ["chat"]),
                           ("now playing", ["now-playing", "nowplaying", "spotify", "song"]),
                           ("sound/media alerts", ["blerp", "media-share", "sound", "channel points"]),
                           ("goal", ["goal"]), ("viewer count", ["view"]), ("event list", ["event"]),
                           ("local page", ["localhost", "127.0.0.1"])]:
            if any(w in u for w in words): return f"widget: {key}"
        return "widget: other"
    if i == "dshow_input":
        n = (s["name"] + st.get("video_device_id", "")).lower()
        if st.get("use_custom_audio_device") or any(w in n for w in ("capture", "elgato", "cam link", "usb2 video", "hdmi", "avermedia")):
            return "device: capture card?"
        return "device: camera"
    return {"wasapi_input_capture": "audio: mic/input", "wasapi_output_capture": "audio: desktop/output",
            "wasapi_process_output_capture": "audio: app", "game_capture": "capture: game",
            "window_capture": "capture: window", "monitor_capture": "capture: screen",
            "ffmpeg_source": "media", "image_source": "image", "text_gdiplus": "text"}.get(i, i)

def summary(s):
    st, out = s["settings"], []
    for k in ("url", "video_device_id", "audio_device_id", "device_id", "window", "resolution", "width", "height"):
        if st.get(k) not in (None, ""): out.append(f"{k}={mask(str(st[k]))}")
    out.append(f"vol={round(s.get('volume', 1.0), 3)}{' MUTED' if s.get('muted') else ''} monitor={s.get('monitoring_type', 0)}")
    fl = [f"{f['name']}({'on' if f.get('enabled', True) else 'off'})" for f in s.get("filters", [])]
    if fl: out.append("filters: " + ", ".join(fl))
    return "; ".join(out)

def cmd_tools(arg):
    p, d = load(arg)
    srcs = {s["name"]: s for s in d["sources"] if s["id"] not in ("scene", "group")}
    canvases = {c["info"]["uuid"]: c["info"]["name"] for c in d.get("canvases", [])}
    seen, hidden = {}, {}
    for sc in (s for s in d["sources"] if s["id"] in ("scene", "group")):
        cv = sc.get("canvas_uuid") or MAIN_CANVAS
        label = sc["name"] if cv == MAIN_CANVAS else f"{sc['name']} [{canvases.get(cv, 'other canvas')}]"
        for it in sc["settings"].get("items", []):
            (seen if it.get("visible") else hidden).setdefault(it["name"], []).append(label)
    print(f"Collection: {d['name']}  ({p})\n")
    print("USED (visible in at least one scene):")
    skip = {"media", "image", "text"}
    used = [n for n in seen if n in srcs]
    for n in sorted(used, key=lambda n: classify(srcs[n])):
        c = classify(srcs[n])
        if c in skip: continue
        print(f"- {n}  <{c}>  {summary(srcs[n])}\n    scenes: {', '.join(seen[n])}")
    print("\nGLOBAL AUDIO (in every scene):")
    for k in GLOBAL_AUDIO:
        if k in d: print(f"- {k}: {d[k]['name']} <{d[k]['id']}> {summary(d[k])}")
    print("\nHIDDEN EVERYWHERE (skip unless the user wants them):")
    for n in sorted(set(hidden) - set(seen)):
        if n in srcs and classify(srcs[n]) not in skip: print(f"- {n} <{classify(srcs[n])}>")
    print("\nDECORATION (the old pack's look; not carried over): "
          + ", ".join(sorted(n for n in used if classify(srcs[n]) in skip))[:600])

def cmd_slots(arg):
    p, d = load(arg)
    srcs = {s["name"]: s for s in d["sources"]}
    print(f"Kit: {d['name']}  ({p})")
    for sc in (s for s in d["sources"] if s["id"] == "scene"):
        cv = sc.get("canvas_uuid") or MAIN_CANVAS
        print(f"\n## {sc['name']}{'' if cv == MAIN_CANVAS else '  (vertical canvas)'}")
        for it in sc["settings"]["items"]:
            s = srcs.get(it["name"], {}); st = s.get("settings", {})
            size = f"box {it['bounds']['x']:.0f}x{it['bounds']['y']:.0f}" if it.get("bounds_type") else \
                   f"src {st.get('width', '?')}x{st.get('height', '?')} @ {it['scale']['x']:.3f}"
            ph = " PLACEHOLDER" if "PASTE_YOUR" in st.get("url", "") or (s.get("id") in ("dshow_input", "wasapi_process_output_capture", "game_capture", "window_capture") and not any(st.values())) else ""
            print(f"  {'  ' if it['visible'] else 'OFF'} {it['name']} <{s.get('id', 'scene')}> at {it['pos']['x']:.0f},{it['pos']['y']:.0f} {size}{ph}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("list", "tools", "slots") or (a[0] != "list" and len(a) < 2): sys.exit(__doc__)
    {"list": lambda: cmd_list(), "tools": lambda: cmd_tools(a[1]), "slots": lambda: cmd_slots(a[1])}[a[0]]()
