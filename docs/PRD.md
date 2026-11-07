# PRD: OBS Brand Kit

## Problem
Paid overlay packs (like "Tokyo Nights") are one-size-fits-all: loud styling, someone else's
fonts and colours, hard-coded widget links, and absolute file paths that break on another PC.
A streamer wants a clean, practical scene collection in *their* brand that imports in one go.

## User
- **Builder** (us): runs the generator once per streamer brand.
- **Streamer** (end user): imports the result into OBS (directly, or via Streamlabs Desktop),
  pastes their own widget URLs, picks their webcam and goes live.

## Goals
1. One `brand.json` per streamer drives everything: name, palette, fonts, logo, socials, style.
2. One command builds the animated assets (EffectCraft) and a themed OBS scene collection.
3. The output imports cleanly on any Windows PC: no absolute paths, no secrets.
4. The same build also produces a Streamlabs `.overlay` file.

Success: the sample brand builds end to end and imports into OBS as a new collection with every
scene, source and asset loading, and a secret scan of the output finds nothing.

## v1 user stories
- *As a builder*, I edit `brand.json` and run `python -m kit build brands/<slug>` →
  `dist/<slug>/` (OBS JSON + assets), `dist/<slug>.zip`, `dist/<slug>.overlay`.
  Accept: missing font or bad colour fails fast with a clear message.
- *As a streamer*, I unzip, then OBS ▸ Scene Collection ▸ Import the JSON. Accept: 6 main scenes
  (Starting, Just Chatting, Gameplay, React, BRB, Ending) plus shared nested scenes appear, all
  media plays, alerts sit in place with `PASTE_YOUR_…` placeholder URLs that render nothing.
- *As a Streamlabs user*, I load the `.overlay` in Streamlabs Desktop. Accept: scenes and media
  load, Streamlabs widgets (alerts, chat, events, viewer count) auto-link to my own account.
  OBS can then import that Streamlabs collection (Scene Collection ▸ Import ▸ Streamlabs).
- *As a streamer*, I re-theme by changing `brand.json` and rebuilding (README explains).

## Structure taken from Tokyo Nights (not its look)
Scenes: Starting, Facecam/Gameplay, Just Chatting (x3 variants → 1), BRB, Match Reacts (→ React),
Ending. Sources kept by role: animated backgrounds, webcam + frame, socials row, alert box,
media/channel-point alerts, chat box, event labels, viewer counts, now-playing, music capture,
stinger transition. Dropped: duplicate copies of each source per scene, the mask/kunai art,
countdown timers, the vertical (Aitum) canvas.

## Non-goals (v1)
Vertical canvas, per-platform widget hosting, a GUI, macOS/Linux paths, custom alert animations
(alerts come from the streamer's own Streamlabs/StreamElements account).

## Constraints
Free tools only (EffectCraft, ffmpeg, Python stdlib). Never read or ship real tokens/URLs from
the reference collection. Never modify the user's live Tokyo Nights collection.

## Open questions
- Should the kit ship a vertical canvas later? (needs OBS 31 canvases or Aitum Vertical)
- Brand fonts that aren't free can't be bundled; the streamer must install them.
