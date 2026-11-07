"""Build a personal OBS collection = a kit collection's look + the user's real tools from their existing collection.

  python tools/obs_connect.py <plan.json> [--replace] [--out <file.json>]

The plan holds names and positions only. Real URLs, device ids and filters are copied from the source collection
at run time, straight into OBS's scenes folder (or --out). Keep the plan and its assets outside this repo:
the tool refuses to write a collection or assets inside it. Guide: docs/CONNECT.md.

Plan (paths may be absolute or relative to the plan file):
{
  "name": "Northwind Live",                        # the new collection's name in OBS
  "file": "Northwind_Live.json",                   # file name in the OBS scenes folder
  "source": "My Stream",                           # the user's existing collection (name or .json path)
  "kit": "<repo>/dist/northwind/Northwind Brand Kit.json",   # built kit collection (./assets/ paths)
  "assets": "assets",                              # where the kit's assets are copied (personal folder)
  "keep_kit": ["Starting Soon (bg)", "..."],         # kit sources that stay (backgrounds, frames, decoration)
  "sources": {                                     # new source name -> copy of a source collection source
    "Webcam": {"from": "MY CAM", "drop_filters": true, "set": {"muted": true}, "settings": {"width": 760}}
  },
  "global_audio": {"AuxAudioDevice1": "AuxAudioDevice1"},   # copied from the source; kit's own defaults dropped
  "scenes": {                                      # every kit scene to keep, in order; items bottom -> top
    "Just Chatting": [["Webcam", {"box": [1920, 1080], "fill": true, "mirror": true}], ["[S] Alerts", {}]]
  }
}
Placement keys: x, y, s (scale), box [w,h] (scale into it), fill (crop to fill the box), crop [l,t,r,b],
mirror (flip horizontally), hidden; {"kit": true} keeps the kit's own placement of that item. Scenes on the kit's vertical canvas use "vertical_canvas" (default [1080,1920]).
"""
import copy, json, os, shutil, sys, uuid

APPDATA = os.environ["APPDATA"]
SCENES = os.path.join(APPDATA, "obs-studio", "basic", "scenes")
REGISTRY = os.path.join(APPDATA, "obs-studio", "obs-connect-tools.json")
MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = uuid.UUID("6f1d3c52-1b0e-4c55-9a51-c10dbe77a11e")

def find_collection(ref, base):
    p = ref if os.path.isabs(ref) else os.path.join(base, ref)
    if ref.lower().endswith(".json") and os.path.exists(p): return p
    for f in os.listdir(SCENES):
        if f.endswith(".json"):
            try:
                if json.load(open(os.path.join(SCENES, f), encoding="utf-8")).get("name") == ref:
                    return os.path.join(SCENES, f)
            except Exception: pass
    sys.exit(f"source collection {ref!r} not found")

def registry():
    try: return json.load(open(REGISTRY, encoding="utf-8"))
    except Exception: return []

def main():
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    plan_path = os.path.abspath(args[0]); base = os.path.dirname(plan_path)
    P = json.load(open(plan_path, encoding="utf-8"))
    rp = lambda x: x if os.path.isabs(x) else os.path.normpath(os.path.join(base, x))
    out_path = rp(args[args.index("--out") + 1]) if "--out" in args else os.path.join(SCENES, P["file"])
    inside = lambda p: os.path.normcase(os.path.abspath(p)).startswith(os.path.normcase(REPO) + os.sep)
    for what, p in (("collection", out_path), ("assets", rp(P["assets"]))):
        if inside(p): sys.exit(f"refusing: the {what} path is inside the kit repo ({p}); it would hold personal data")
    src_path = find_collection(P["source"], base)
    if os.path.abspath(out_path) == os.path.abspath(src_path): sys.exit("refusing: output = source collection")
    if os.path.exists(out_path):
        cur = json.load(open(out_path, encoding="utf-8")).get("name")
        if "--replace" not in args: sys.exit(f"{out_path} exists; pass --replace to rebuild it")
        if out_path.startswith(SCENES) and (cur != P["name"] or cur not in registry()):
            sys.exit(f"refusing to replace {cur!r}: only collections this tool made can be replaced")
    elif out_path.startswith(SCENES):
        for f in os.listdir(SCENES):  # a different file already holding this name would confuse OBS
            if f.endswith(".json") and json.load(open(os.path.join(SCENES, f), encoding="utf-8")).get("name") == P["name"]:
                sys.exit(f"a collection named {P['name']!r} already exists ({f})")

    kit_path = rp(P["kit"]); assets = rp(P["assets"])
    kit = json.load(open(kit_path, encoding="utf-8"))
    src = json.load(open(src_path, encoding="utf-8"))
    S = {s["name"]: s for s in src["sources"] if s["id"] not in ("scene", "group")}

    shutil.copytree(os.path.join(os.path.dirname(kit_path), "assets"), assets, dirs_exist_ok=True)
    def absolutize(o):
        if isinstance(o, dict): return {k: absolutize(v) for k, v in o.items()}
        if isinstance(o, list): return [absolutize(v) for v in o]
        if isinstance(o, str) and o.startswith("./assets/"):
            return os.path.join(assets, o[len("./assets/"):]).replace("\\", "/")
        return o
    kit = absolutize(kit)
    K = {s["name"]: s for s in kit["sources"]}

    srcs = {}
    for n in P.get("keep_kit", []):
        if n not in K: sys.exit(f"keep_kit: {n!r} is not in the kit")
        srcs[n] = copy.deepcopy(K[n])
    for n, spec in P["sources"].items():
        if spec["from"] not in S: sys.exit(f"sources.{n}: {spec['from']!r} is not in {P['source']!r}")
        s = copy.deepcopy(S[spec["from"]])
        s["name"], s["uuid"] = n, str(uuid.uuid5(NS, n))
        s.pop("canvas_uuid", None)
        if spec.get("drop_filters"): s["filters"] = []
        s["settings"].update(spec.get("settings", {}))
        s.update(spec.get("set", {}))
        srcs[n] = s

    W, H = kit.get("resolution", {}).get("x", 1920), kit.get("resolution", {}).get("y", 1080)
    VW, VH = P.get("vertical_canvas", [1080, 1920])
    scene_uuid, scenes = {}, []
    for name, items in P["scenes"].items():
        if name not in K or K[name]["id"] != "scene": sys.exit(f"scenes: {name!r} is not a kit scene")
        b = copy.deepcopy(K[name]); scene_uuid[name] = b["uuid"]
        scenes.append((b, items, (b.get("canvas_uuid") or MAIN_CANVAS) != MAIN_CANVAS))

    def item(name, v, x=0, y=0, s=1.0, box=None, fill=False, crop=(0, 0, 0, 0), mirror=False, hidden=False):
        sx = sy = float(s)
        bw, bh = box or (0, 0)
        if mirror:
            sx = -sx
            if not box:  # unbounded flips anchor on the right edge; bounded ones flip inside their box
                x = x + srcs[name]["settings"].get("width", 1920) * s
        cw, ch = (VW, VH) if v else (W, H)
        it = {"name": name, "source_uuid": srcs[name]["uuid"] if name in srcs else scene_uuid[name],
              "visible": not hidden, "locked": False, "rot": 0.0, "pos": {"x": float(x), "y": float(y)},
              "scale": {"x": sx, "y": sy}, "align": 5,
              "bounds_type": (3 if fill else 2) if box else 0, "bounds_align": 0, "bounds_crop": bool(fill),
              "bounds": {"x": float(bw), "y": float(bh)},
              "crop_left": crop[0], "crop_top": crop[1], "crop_right": crop[2], "crop_bottom": crop[3],
              "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
              "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
              "private_settings": {}, "group_item_backup": False,
              # OBS 31+ relative coords; without them items on a plugin canvas (Aitum) render nowhere
              "pos_rel": {"x": (2 * x - cw) / ch, "y": 2 * y / ch - 1.0}, "scale_rel": {"x": sx, "y": sy},
              "scale_ref": {"x": float(cw), "y": float(ch)}, "bounds_rel": {"x": 2 * bw / ch, "y": 2 * bh / ch}}
        return it

    for b, items, v in scenes:
        its = []
        kit_items = {it["name"]: it for it in b["settings"]["items"]}
        for i, (n, kw) in enumerate(items, 1):
            if n not in srcs and n not in scene_uuid: sys.exit(f"scene {b['name']!r}: unknown item {n!r}")
            if kw.get("kit"):  # the kit's own placement, untouched (alignment, crop, scale and all)
                if n not in kit_items: sys.exit(f"scene {b['name']!r}: {n!r} has no kit placement to keep")
                it = copy.deepcopy(kit_items[n]); it["visible"] = not kw.get("hidden", False)
            else:
                it = item(n, v, **kw)
            it["id"] = i; its.append(it)
        b["settings"]["items"], b["settings"]["id_counter"] = its, len(its)

    out = copy.deepcopy(kit)
    out["name"] = P["name"]
    out["sources"] = list(srcs.values()) + [b for b, _, _ in scenes]
    for k in [k for k in out if k.startswith(("DesktopAudioDevice", "AuxAudioDevice"))]: out.pop(k)
    for k, frm in P.get("global_audio", {}).items():
        if frm not in src: sys.exit(f"global_audio: {frm!r} is not in the source collection")
        out[k] = copy.deepcopy(src[frm])
    main_scenes = [b["name"] for b, _, v in scenes if not v]
    out["current_scene"] = out["current_program_scene"] = main_scenes[0]
    out["scene_order"] = [{"name": n} for n in main_scenes if not n.startswith("[S]")] + \
                         [{"name": n} for n in main_scenes if n.startswith("[S]")]
    if "PASTE_YOUR" in json.dumps(out): print("note: a kit placeholder widget is still in the collection")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    if out_path.startswith(SCENES):
        reg = registry()
        if P["name"] not in reg: json.dump(reg + [P["name"]], open(REGISTRY, "w", encoding="utf-8"), indent=1)
    print(f"wrote {out_path}: {len(srcs)} sources, {len(scenes)} scenes ({sum(v for *_, v in scenes)} vertical)")

if __name__ == "__main__":
    main()
