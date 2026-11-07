"""layout -> Streamlabs Desktop .overlay (a zip: config.json + asset files at its root).

Node schema from stream-labs/desktop app/services/scene-collections/nodes/overlays/*.ts.
Slot positions are fractions of the base resolution; scale is stored as scale / base size.
Items are listed bottom -> top, like OBS. Widgets carry no URL: on load Streamlabs links the
importing user's own widget of that type. Sources with no Streamlabs node (plain browser
sources without a widget equivalent, window capture, app audio) are left out.
"""
import json, os, uuid, zipfile

from . import layout
from .obs import source_size

NS = uuid.UUID("0b6f2a7e-1c55-4f0e-a7a4-2d6a0f7c3e91")
W, H = layout.W, layout.H

def node(kind, version, **data):
    return {"schemaVersion": version, "nodeType": kind, **data}

def _id(slug, *parts):
    return str(uuid.uuid5(NS, "/".join((slug,) + parts)))

def content(b, s, assets, scene_ids, name):
    k = s["kind"]
    if k == "media":
        return node("VideoNode", 1, filename=assets[s["asset"]]["file"], settings={
            "is_local_file": True, "local_file": "", "looping": s["loop"], "restart_on_activate": True,
            "clear_on_media_end": s["clear_end"], "close_when_inactive": True})
    if k == "image":
        return node("ImageNode", 1, filename=assets[s["asset"]]["file"])
    if k == "text":
        from .brand import obs_color
        return node("TextNode", 1, settings={
            "text": s["text"], "font": {"face": s["font"], "size": s["size"], "style": "Regular", "flags": 0},
            "color": obs_color(s["color"]), "align": "center", "valign": "center",
            "gradient": False, "custom_font": "", "file": "",
            **({"outline": True, "outline_size": 6, "outline_color": obs_color(s["outline"]), "outline_opacity": 100} if s.get("outline") else {"outline": False})})
    if k == "browser" and s["sl_widget"] is not None:
        return node("WidgetNode", 1, type=s["sl_widget"], settings={
            "width": s["w"], "height": s["h"], "shutdown": False, "restart_when_active": False})
    if k == "game":
        return node("GameCaptureNode", 2, width=W, height=H)
    if k == "scene":
        return node("SceneSourceNode", 2, sceneId=scene_ids[name], width=W, height=H)
    return None  # webcam handled by caller; others have no node

def slot(b, it, s, assets, scene_ids, scene_name, idx):
    x, y = it["x"], it["y"]
    sx = sy = 1.0
    if s["kind"] == "webcam":
        c = node("WebcamNode", 1, width=it["w"] / W, height=it["h"] / H)
    else:
        c = content(b, s, assets, scene_ids, it["source"])
        if c is None:
            return None
        size = source_size(s)
        if size and it["w"] and not it["bounds"]:
            sx, sy = it["w"] / size[0], it["h"] / size[1]
        if it["center"] and s["kind"] == "text":  # Streamlabs positions are top-left
            est_w = 0.5 * s["size"] * len(s["text"])
            x, y = x - est_w / 2, y - s["size"] * 0.65
    return {
        "id": _id(b.slug, scene_name, str(idx)), "name": it["source"], "sceneNodeType": "item",
        "x": x / W, "y": y / H, "scaleX": sx / W, "scaleY": sy / H,
        "crop": {"top": 0, "bottom": 0, "left": 0, "right": 0}, "rotation": 0,
        "visible": it["visible"], "locked": False, "filters": [], "mixerHidden": False,
        "content": c,
    }

def config(b, assets):
    srcs = layout.sources(b, assets)
    scenes = layout.scenes(b, assets)
    scene_ids = {name: "scene_" + _id(b.slug, "scene", name) for name, _ in scenes}
    dropped = set()
    items = []
    for name, its in scenes:
        slots = []
        for i, it in enumerate(its):
            sl = slot(b, it, srcs[it["source"]], assets, scene_ids, name, i)
            if sl is None:
                dropped.add(it["source"])
            else:
                slots.append(sl)
        items.append({"name": name, "sceneId": scene_ids[name], "slots": node("SlotsNode", 1, items=slots)})
    from .assets import STINGER_POINT_MS
    root = node("RootNode", 2,
                scenes=node("ScenesNode", 2, items=items),
                transition=node("TransitionNode", 1, type="obs_stinger_transition", duration=300, settings={
                    "path": assets["stinger"]["file"], "tp_type": 0, "transition_point": assets["stinger"].get("point_ms", STINGER_POINT_MS),
                    "audio_monitoring": 0, "audio_fade_style": 0, "preload": True}),
                nodeMap=node("NodeMapNode", 1))
    return root, sorted(dropped)

def write(b, assets, assets_dir, out_path):
    root, dropped = config(b, assets)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("config.json", json.dumps(root, indent=2))
        for a in assets.values():
            z.write(os.path.join(assets_dir, a["file"]), a["file"])
    return dropped
