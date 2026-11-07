# Architecture essentials (read first)

**What:** `brand.json` → EffectCraft-rendered assets + OBS scene collection JSON + Streamlabs `.overlay`.
Detail: `docs/ARCHITECTURE.md`. Product: `docs/PRD.md`.

## Stack
Python 3 stdlib · EffectCraft CLI (newest `effectcraft-*-portable` under `~/Documents/Claude/Artcraft`) · ffmpeg (VP9 alpha WebM).

## Map
- `brands/<slug>/` — `brand.json`, logo, optional fonts. One per streamer.
- `kit/brand.py` load/validate · `kit/ec.py` EffectCraft driver · `kit/assets.py` comps
- `kit/layout.py` the scene spec (single source of truth for both outputs)
- `kit/obs.py` OBS JSON · `kit/streamlabs.py` `.overlay` · `kit/check.py` safety checks
- `kit/__main__.py` CLI: `python -m kit build brands/<slug> [--skip-render]`
- `tools/obs_inventory.py`, `tools/obs_connect.py`, `tools/obs_connect_check.py`, `tools/leak_scan.py` —
  connect a built kit to the tools in the streamer's existing collection (`docs/CONNECT.md`)
- `dist/<slug>/` output (OBS JSON + `assets/` + `fonts/` + `IMPORT.md`), `dist/<slug>.zip`, `dist/<slug>.overlay`

## Invariants
- Every file path in the OBS JSON starts with `./` (OBS importer resolves it next to the JSON).
- Every widget URL is `about:blank#PASTE_YOUR_…_URL`; `.overlay` widget URLs are empty.
- Canvas 1920×1080; layout coordinates are canvas pixels; scale = target size / asset size.
- Restrained style: one accent colour, thin strokes, slow motion. No glow, no particles.
- Colours in OBS JSON are ABGR integers (`0xAABBGGRR`).
- Vertical scenes: name `<Scene> (V)`, `canvas_uuid` of the canvas named exactly "Aitum Vertical",
  never in `scene_order`; horizontal scenes link to them via `settings.canvas`. A `(horizontal only)`
  copy ships for OBS ≤ 30. Layout in `layout.vertical_scenes`, 1080×1920.
- Every scene item carries relative coordinates (`pos_rel`, `scale_rel`, `scale_ref`, `bounds_rel`) for
  its own canvas, or plugin-canvas scenes render black.

## Don't
- Don't read, copy or print anything from `%APPDATA%\obs-studio\basic\scenes\Toyko_Nights*` beyond structure.
  Sole exception: `tools/obs_connect.py` copies a collection's sources straight into a personal collection in
  OBS's scenes folder, on the streamer's own PC; it refuses to write inside this repo.
- Don't write into `%APPDATA%\obs-studio` except a clearly named test collection or a personal collection
  made by `tools/obs_connect.py`, and restore `user.ini`.
- Don't use ports 4420–4519 (Windows reserved range). OBS websocket is on 4600.
- Don't add pip dependencies (GitHub-first + repo-vetting first).
