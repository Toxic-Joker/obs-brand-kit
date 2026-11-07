"""Write the OBS collection, the Streamlabs .overlay, the end-user guide, then zip and check."""
import json, os, shutil, sys, zipfile

from . import obs, streamlabs, check

GUIDE = os.path.join(os.path.dirname(__file__), "IMPORT.template.md")

def build(b, work, assets):
    coll_name = f"{b.name} Brand Kit"
    dist = work.dist
    json_name = f"{coll_name}.json"
    coll = obs.collection(b, assets, coll_name)
    with open(os.path.join(dist, json_name), "w", encoding="utf-8") as f:
        json.dump(coll, f, indent=2, ensure_ascii=False)
    has_vertical = "canvases" in coll
    for f in ("Add vertical stinger.ps1", "Add vertical stinger.cmd"):
        if os.path.exists(os.path.join(dist, f)):
            os.remove(os.path.join(dist, f))
    if has_vertical:  # installer for the Aitum Vertical transition list (lives outside the collection)
        tpl = open(os.path.join(os.path.dirname(__file__), "vertical-stinger.template.ps1"), encoding="utf-8").read()
        ps1 = (tpl.replace("{{NAME}}", obs.vertical_stinger_name(b)).replace("{{FILE}}", assets["stinger_v"]["file"])
                  .replace("{{POINT}}", str(assets["stinger_v"].get("point_ms", 600))))
        with open(os.path.join(dist, "Add vertical stinger.ps1"), "w", encoding="utf-8-sig") as f:
            f.write(ps1)
        cmd = ["@echo off", 'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Add vertical stinger.ps1"', "pause", ""]
        with open(os.path.join(dist, "Add vertical stinger.cmd"), "wb") as f:
            f.write("".join(x + chr(13) + chr(10) for x in cmd if x).encode("ascii"))
    h_name = f"{coll_name} (horizontal only).json"
    h_path = os.path.join(dist, h_name)
    if has_vertical:  # for OBS older than 31, which has no canvases and would mix the vertical scenes in
        h_coll = obs.collection(b, assets, coll_name, vertical=False)
        with open(h_path, "w", encoding="utf-8") as f:
            json.dump(h_coll, f, indent=2, ensure_ascii=False)
    elif os.path.exists(h_path):
        os.remove(h_path)

    fonts_dir = os.path.join(dist, "fonts")
    shutil.rmtree(fonts_dir, ignore_errors=True)
    for ff in b.fonts["files"]:
        os.makedirs(fonts_dir, exist_ok=True)
        shutil.copy2(os.path.join(b.dir, ff), fonts_dir)

    overlay = os.path.join(os.path.dirname(dist), f"{coll_name}.overlay")
    dropped = streamlabs.write(b, assets, work.assets, overlay)

    guide = open(GUIDE, encoding="utf-8").read()
    fonts_line = (f"Install the fonts in `fonts/` first (right-click > Install for all users)."
                  if b.fonts["files"] else
                  f"The kit's text uses **{b.fonts['body']}**. If it isn't installed, OBS shows Arial instead.")
    guide = (guide.replace("{{NAME}}", coll_name).replace("{{JSON}}", json_name)
                  .replace("{{OVERLAY}}", os.path.basename(overlay)).replace("{{FONTS}}", fonts_line)
                  .replace("{{DROPPED}}", ", ".join(dropped) or "nothing")
                  .replace("{{HJSON}}", h_name)
                  .replace("{{VPOINT}}", str(assets.get("stinger_v", {}).get("point_ms", 600))))
    if not has_vertical:  # drop the vertical section from the guide
        guide = guide.split("<!-- vertical -->")[0] + guide.split("<!-- /vertical -->")[-1]
    guide = guide.replace("<!-- vertical -->", "").replace("<!-- /vertical -->", "")
    with open(os.path.join(dist, "IMPORT.md"), "w", encoding="utf-8") as f:
        f.write(guide)

    zip_path = os.path.join(os.path.dirname(dist), f"{coll_name} (OBS).zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(dist):
            for fn in files:
                if fn == "assets.json":
                    continue
                p = os.path.join(root, fn)
                z.write(p, os.path.join(coll_name, os.path.relpath(p, dist)))

    problems = check.check_obs(coll, dist) + check.check_overlay(overlay)
    if has_vertical:
        problems += check.check_obs(h_coll, dist)
    print(f"\nOBS collection : {os.path.join(dist, json_name)}"
          + ("  (+ vertical canvas, + horizontal-only copy)" if has_vertical else ""))
    print(f"OBS zip        : {zip_path}")
    print(f"Streamlabs     : {overlay}  (left out: {', '.join(dropped) or 'nothing'})")
    if problems:
        print("\nCHECKS FAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("Checks         : OK (no web URLs, no local paths, no tokens, every file present)")
