# {{NAME}} — how to install

## Option A: OBS Studio (recommended)
1. Unzip this folder somewhere **permanent** (for example `Documents\Streaming\{{NAME}}`).
   OBS links to the files here, so don't move or delete the folder afterwards.
2. {{FONTS}}
3. In OBS: **Scene Collection ▸ Import**. Click **…** under *Collection Path* and pick
   `{{JSON}}` in this folder. Tick it, click **Import**.
4. **Scene Collection ▸ {{NAME}}** to switch to it. Your other collections are not touched.
5. Set your base (canvas) resolution to **1920×1080** (Settings ▸ Video).

<!-- vertical -->
### Vertical (TikTok / Shorts) — automatic if you use Aitum Vertical
The collection also holds 1080×1920 versions of every scene (`Starting Soon (V)`, `Just Chatting (V)`,
`Gameplay (V)`, `React (V)`, `Be Right Back (V)`, `Ending (V)`) on a vertical canvas.
- **You use the Aitum Vertical plugin (OBS 31 or newer):** they appear in its dock by themselves.
  Switching a horizontal scene switches its vertical twin too. They share your webcam, alert box and
  music with the horizontal scenes, so you set those up once.
- **Vertical transition:** close OBS, then double-click `Add vertical stinger.cmd` in this folder (once).
  It adds the brand stinger to Aitum's transition list; the vertical scenes are already set to use it.
  Only that list changes (your Aitum stream keys and other settings stay as they are; a copy of the
  old settings is kept as `config.json.before-kit`). Until you run it, vertical uses Aitum's default.
- **You don't use Aitum Vertical:** nothing changes. The vertical scenes stay hidden and use no resources.
- **OBS 30 or older:** import `{{HJSON}}` instead, so the vertical scenes don't mix into your list.
<!-- /vertical -->

## Option B: Streamlabs Desktop
1. Streamlabs: **Settings ▸ Scene Collections ▸ Import Overlay File**, pick `{{OVERLAY}}`.
   Streamlabs creates a new collection and links its own widgets (alert box, chat box, event list,
   viewer count, sub goal) to *your* Streamlabs account automatically.
   Streamlabs gives each scene its own copy of the images and videos (same files, so it costs
   nothing). Webcam and widgets stay shared.
2. Left out of the `.overlay` (Streamlabs has no slot for them): {{DROPPED}}.
   Add them by hand if you want them, or use Option A.
3. To move it to OBS later: in OBS, **Scene Collection ▸ Import**, then the *Streamlabs* entry it
   finds automatically (or browse to `%APPDATA%\slobs-client\SceneCollections`).

## Connect your own accounts (Option A)
Every widget is a Browser Source whose URL reads `about:blank#PASTE_YOUR_…_URL`. It shows nothing
until you fill it in. Double-click the source, replace the whole URL with your own link:

| Source | Where it is | Paste |
|---|---|---|
| Alert Box | scene `[S] Alerts` (shown in every scene) | Streamlabs / StreamElements alert box URL |
| Media / Sound Alerts | `[S] Alerts` | Blerp, channel-points or media-share URL |
| Chat Box | Just Chatting, React (hidden in Gameplay) | chat widget URL |
| Latest Events | Gameplay | event list / recent follower URL |
| Viewer Count | React (hidden in Gameplay) | viewer count widget URL |
| Sub / Tip / Bits Goal | Just Chatting (some hidden) | goal widget URLs |
| Now Playing | Just Chatting | now-playing widget URL |

Because the alerts live in the nested `[S] Alerts` scene, you paste each link **once**.
Keep your widget URLs private: they contain your account key.

## Set your devices
- **Webcam**: double-click *Webcam* in any scene and pick your camera (shared by all scenes).
- **Game Capture** (Gameplay) and **Content (pick a window)** (React): pick the game/window.
- **Music (pick the app)** in `[S] Audio`: pick Spotify or your music player.
- Mic and desktop audio use your Windows default devices (Settings ▸ Audio to change).

## Scenes
Starting Soon · Just Chatting · Gameplay · React · Be Right Back · Ending, plus the shared
`[S] Alerts` and `[S] Audio` scenes nested inside them. The transition is the brand stinger.
The **Lower Third** in Just Chatting plays when you switch to the scene; toggle its eye icon
to play it again. Edit **Topic (edit me)** on Starting Soon before each stream.
