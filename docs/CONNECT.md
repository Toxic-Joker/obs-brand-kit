# Connect a kit to the tools you already use

A built kit ships generic placeholders (`about:blank#PASTE_YOUR_…_URL`, an empty camera, no mic). If your
OBS already has a scene collection with your real alert box, chat, now-playing widget, sound alerts,
camera, capture card and audio, the connect tools build a **personal** copy of the kit wired to them:
the kit's look and positions, your tools, nothing you don't use.

The personal collection lives only in OBS's scenes folder. Your URLs and tokens never enter this repo:
the plan file holds names and positions, and `obs_connect.py` refuses to write a collection or its
assets inside the repo. No existing collection with real tools → nothing to connect; use the kit as built.

| Tool | Does |
|---|---|
| `tools/obs_inventory.py list` | lists your collections: which is active, which hold real devices/widgets |
| `tools/obs_inventory.py tools "<collection>"` | what that collection really uses (visible in a scene), per scene, URLs masked; read-only |
| `tools/obs_inventory.py slots "<kit>.json"` | the kit's scenes, slots, positions and sizes |
| `tools/obs_connect.py <plan.json>` | builds the personal collection from the plan (`--replace` rebuilds one it made) |
| `tools/obs_connect_check.py "<name>" --out <dir>` | opens OBS on it, screenshots every scene, switches OBS back, checks no other collection changed |
| `tools/leak_scan.py "<collection>" <folders…>` | finds any of that collection's URL tokens in files (shown masked) |

Run the tools with `python -I`, except `obs_connect_check.py`, which needs the `websockets` package
(`pip install websockets`) and OBS closed.

## Steps

1. `obs_inventory.py list`, pick your existing collection.
2. `obs_inventory.py tools "<it>"`: decide what carries over. Leave out what's hidden everywhere, the old
   pack's decoration, leftovers (a window capture of a random tab) and duplicates (two chats: keep one).
3. `obs_inventory.py slots "dist/<slug>/<Name> Brand Kit.json"`: give every tool a scene and slot; drop
   every kit slot nothing fills.
4. Write `plan.json` in a folder of your own, outside the repo (format in `tools/obs_connect.py`).
5. `obs_connect.py plan.json`, then `obs_connect_check.py "<name>" --out <dir>` and look at the screenshots.
   Adjust the plan, rebuild with `--replace`.
6. In OBS pick the new collection under **Scene Collection**. Your old collection is untouched.
7. Optional: `leak_scan.py "<old collection>" <repo> <plan folder>` before sharing anything.

If baked art (cam-frame tag, lower third) shows a handle that isn't yours, build a copy of the brand in
`private/brands/<slug>-<you>/` with your `handle` **and its own `name`**: the name sets
`dist/<Name> Brand Kit (OBS).zip`, so a copy with the same name overwrites the original's zip.

## Plan rules

- **Sources** are copied from your collection (`"from"`), so URLs, device ids, volume, monitoring and
  filters come along. `settings` and `set` override single values (e.g. a browser size, `muted`).
- **Shared layers:** alerts and sound/media alerts go in `[S] Alerts`, music app audio in `[S] Audio`,
  so they reach every scene.
- **Mics and voice apps** go where your collection had them (often the live scenes only). The kit's
  default `Desktop Audio` and `Mic/Aux` are always dropped; copy your collection's global audio with
  `global_audio` only when it's a real device (`wasapi_*`), not a plugin wrapper.
- **Camera:** `"mirror": true` when your collection mirrored it (negative x scale). A camera's own mic also
  feeds the mixer (`dshow_input` with `audio_output_mode` 0): mute it with `"set": {"muted": true}` unless you use it.
- **Capture card / game** takes the kit's `Game Capture` slot (`"box"` = the full canvas).
- **Widget size:** a browser source renders text at its own pixel size, so set `settings.width/height`
  so that slot size ÷ browser size ≈ the scale your collection used (a chat shown at ~0.5 scale in a
  388×507 slot → 760×1000). Keep your crop for cropped cards (`"crop": [l, t, r, b]`).
- **Placement keys:** `x`, `y`, `s` (scale), `box` `[w, h]` (scale into it), `fill` (crop to fill the
  box), `crop`, `mirror`, `hidden`. `{"kit": true}` keeps the kit's own placement (alignment and all),
  the way to keep the kit's backgrounds, panels, frames and socials. Vertical `(V)` scenes use the 1080×1920 canvas.
- **Expected blanks** in screenshots: widgets that wait for a helper app (Streamer.bot, a now-playing
  bridge) and `localhost` pages whose app isn't running.

## How it stays safe

- Your existing collection is only read. `obs_connect.py` refuses to write over it, over any collection it
  didn't make (it keeps a list in `%APPDATA%\obs-studio\obs-connect-tools.json`), or inside this repo.
- `obs_connect_check.py` backs up `user.ini` and Aitum Vertical's config (stream keys: copied byte for
  byte, never read), restores both, then deletes the `user.ini` copy, which holds widget tokens.
- OBS flips a bounded item inside its box, so a mirrored camera keeps its slot position;
  `obs_connect.py` also writes OBS 31+ relative coordinates, without which vertical-canvas items vanish.
