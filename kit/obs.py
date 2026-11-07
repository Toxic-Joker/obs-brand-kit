"""layout -> OBS Studio scene collection JSON.

File paths are written as ./assets/<file>. OBS's importer (Scene Collection > Import) turns every
string that starts with ./ into an absolute path next to the imported JSON
(obs-studio frontend/importers/studio.cpp, TranslatePaths).
"""
import uuid

from . import layout
from .brand import obs_color

ALIGN_TOP_LEFT, ALIGN_CENTER = 5, 0
BOUNDS_SCALE_INNER, BOUNDS_SCALE_OUTER = 2, 3
CANVAS_PROGRAM_FLAGS = 14  # ACTIVATE | MIX_AUDIO | SCENE_REF, as OBS saves the Aitum Vertical canvas
NS = uuid.UUID("6f1c3a52-6d1e-4c2b-9b7e-0b5e2d6c9a10")

def _uuid(brand_slug, name):
    return str(uuid.uuid5(NS, f"{brand_slug}/{name}"))

def _source(b, name, sid, settings, audio=False, vid=None):
    return {
        "name": name, "uuid": _uuid(b.slug, name), "id": sid, "versioned_id": vid or sid,
        "settings": settings, "mixers": 255 if audio else 0, "sync": 0, "flags": 0, "volume": 1.0,
        "balance": 0.5, "enabled": True, "muted": False, "push-to-mute": False, "push-to-mute-delay": 0,
        "push-to-talk": False, "push-to-talk-delay": 0, "hotkeys": {}, "deinterlace_mode": 0,
        "deinterlace_field_order": 0, "monitoring_type": 0, "private_settings": {}, "filters": [],
    }

def _input(b, name, s, assets):
    k = s["kind"]
    if k == "media":
        return _source(b, name, "ffmpeg_source", {
            "is_local_file": True, "local_file": "./assets/" + assets[s["asset"]]["file"],
            "looping": s["loop"], "restart_on_activate": True, "clear_on_media_end": s["clear_end"],
            "close_when_inactive": True, "hw_decode": False}, audio=s["asset"] == "stinger")
    if k == "image":
        return _source(b, name, "image_source", {"file": "./assets/" + assets[s["asset"]]["file"]})
    if k == "text":
        return _source(b, name, "text_gdiplus", {
            "text": s["text"], "font": {"face": s["font"], "size": s["size"], "style": "Regular", "flags": 0},
            "color": obs_color(s["color"]), "align": "center", "valign": "center", "antialiasing": True,
            **({"outline": True, "outline_size": 6, "outline_color": obs_color(s["outline"]), "outline_opacity": 100} if s.get("outline") else {})},
            vid="text_gdiplus_v3")
    if k == "webcam":
        return _source(b, name, "dshow_input", {}, audio=True)
    if k == "game":
        return _source(b, name, "game_capture", {"capture_mode": "any_fullscreen"}, audio=False)
    if k == "window":
        return _source(b, name, "window_capture", {"method": 0})
    if k == "app_audio":
        return _source(b, name, "wasapi_process_output_capture", {}, audio=True)
    if k == "browser":
        return _source(b, name, "browser_source", {
            "url": s["url"], "width": s["w"], "height": s["h"], "fps_custom": False,
            "reroute_audio": s["audio"], "shutdown": False, "restart_when_active": False,
            "css": "body { background-color: rgba(0, 0, 0, 0); margin: 0px auto; overflow: hidden; }"},
            audio=s["audio"])
    raise ValueError(k)

def source_size(s):
    if s["kind"] in ("media", "image", "browser"):
        return s["w"], s["h"]
    if s["kind"] == "scene":
        return layout.W, layout.H
    return None

def _relative(px, py, sx, sy, bw, bh, cw, ch):
    """OBS 31+ relative coordinates (libobs/obs-scene.c pos_from_absolute / size_from_absolute):
    height maps to [-1, 1]. Without them OBS converts pixels using the canvas size at load time, which
    is 0 for a plugin canvas (Aitum Vertical gets its video only after loading): every item would
    land nowhere and the scene would render black."""
    return {"pos_rel": {"x": (2 * px - cw) / ch, "y": 2 * py / ch - 1.0},
            "scale_rel": {"x": sx, "y": sy}, "scale_ref": {"x": float(cw), "y": float(ch)},
            "bounds_rel": {"x": 2 * bw / ch, "y": 2 * bh / ch}}

def _item(b, it, n, srcs, canvas=(layout.W, layout.H)):
    s = srcs[it["source"]]
    sx = sy = 1.0
    size = source_size(s)
    if size and it["w"] and not it["bounds"]:
        sx, sy = it["w"] / size[0], it["h"] / size[1]
    bounded = it["bounds"] and it["w"]
    return {
        "name": it["source"], "source_uuid": _uuid(b.slug, it["source"]), "id": n,
        "visible": it["visible"], "locked": False, "rot": 0.0,
        "pos": {"x": float(it["x"]), "y": float(it["y"])}, "scale": {"x": sx, "y": sy},
        "align": ALIGN_CENTER if it["center"] else ALIGN_TOP_LEFT,
        "bounds_type": (BOUNDS_SCALE_OUTER if it.get("fill") else BOUNDS_SCALE_INNER) if bounded else 0,
        "bounds_align": 0, "bounds_crop": bool(it.get("fill")),
        "bounds": {"x": float(it["w"] if bounded else 0), "y": float(it["h"] if bounded else 0)},
        "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
        "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
        "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
        "private_settings": {}, "group_item_backup": False,
        **_relative(float(it["x"]), float(it["y"]), sx, sy, float(it["w"] if bounded else 0),
                    float(it["h"] if bounded else 0), *canvas),
    }

def vertical_stinger_name(b):
    return f"{b.name} Stinger (V)"

def collection(b, assets, name, vertical=True):
    """vertical: add the 1080x1920 scenes on a canvas named "Aitum Vertical". OBS 31+ restores the
    canvas from the file before loading scenes, so the scenes stay on it: the Aitum Vertical plugin
    picks them up by the canvas name, and without the plugin they stay hidden and inert."""
    srcs = layout.sources(b, assets)
    scenes = layout.scenes(b, assets)
    vscenes = layout.vertical_scenes(b, assets) if vertical else []
    used = {it["source"] for _, items in scenes + vscenes for it in items}
    out = []
    for sname, spec in srcs.items():
        if spec["kind"] != "scene" and sname in used:
            out.append(_input(b, sname, spec, assets))
    vnames = {n for n, _ in vscenes}
    for sname, items in scenes:
        settings = {"custom_size": False, "id_counter": len(items),
                    "items": [_item(b, it, i + 1, srcs) for i, it in enumerate(items)]}
        if sname + layout.V in vnames:  # Aitum switches the vertical scene along with this one
            settings["canvas"] = [{"width": layout.VW, "height": layout.VH, "scene": sname + layout.V}]
        out.append(_source(b, sname, "scene", settings))
    canvas_uuid = _uuid(b.slug, "canvas/" + layout.VERTICAL_CANVAS)
    for sname, items in vscenes:
        scene = _source(b, sname, "scene", {"custom_size": False, "id_counter": len(items),
                                            "items": [_item(b, it, i + 1, srcs, (layout.VW, layout.VH))
                                                      for i, it in enumerate(items)]})
        scene["canvas_uuid"] = canvas_uuid
        # Aitum's per-scene transition override: the brand stinger, once "Add vertical stinger" has put it
        # in the plugin's transition list (falls back to the plugin's default until then)
        scene["private_settings"] = {"transition": vertical_stinger_name(b), "transition_duration": 1000}
        out.append(scene)
    desktop = _source(b, "Desktop Audio", "wasapi_output_capture", {"device_id": "default"}, audio=True)
    mic = _source(b, "Mic/Aux", "wasapi_input_capture", {"device_id": "default"}, audio=True)
    from .assets import STINGER_POINT_MS
    return {
        "name": name,
        "sources": out,
        "groups": [],
        "scene_order": [{"name": s} for s, _ in scenes],
        "current_scene": layout.FIRST_SCENE,
        "current_program_scene": layout.FIRST_SCENE,
        "DesktopAudioDevice1": desktop,
        "AuxAudioDevice1": mic,
        "transitions": [{"name": f"{b.name} Stinger", "id": "obs_stinger_transition", "settings": {
            "path": "./assets/" + assets["stinger"]["file"], "tp_type": 0,
            "transition_point": assets["stinger"].get("point_ms", STINGER_POINT_MS), "audio_monitoring": 0, "audio_fade_style": 0,
            "track_matte_enabled": False, "preload": True}}],
        "current_transition": f"{b.name} Stinger",
        "transition_duration": 300,
        "quick_transitions": [],
        "saved_projectors": [],
        "preview_locked": False,
        "scaling_enabled": False,
        "resolution": {"x": layout.W, "y": layout.H},
        "modules": {},
        **({"canvases": [{"info": {"name": layout.VERTICAL_CANVAS, "uuid": canvas_uuid, "private": False,
                                   "flags": CANVAS_PROGRAM_FLAGS}}]} if vscenes else {}),
    }
