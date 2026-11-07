# OBS Brand Kit — agent notes

Generates a brandable, restrained OBS scene collection (and a Streamlabs `.overlay`) from one
`brand.json`, with motion assets rendered by EffectCraft. Read `docs/ARCHITECTURE-ESSENTIALS.md`
first; `docs/PRD.md` for scope; `docs/ARCHITECTURE.md` for format details.

## Commands
- Build a brand: `python -m kit build brands/northwind`
- Rebuild only the collection/package (reuse rendered assets): `python -m kit build brands/northwind --skip-render`
- Checks: `python -m unittest discover -s tests`

## Conventions
- Stdlib only. Scene/source structure lives in `kit/layout.py`; `obs.py` and `streamlabs.py` only translate it.
- New asset = a function in `kit/assets.py` returning `(filename, w, h)`; register it in `ASSETS`.
- Keep motion calm: eased 0.3–0.6 s moves, no constant flashing.

## Boundaries
- Never ship real URLs, tokens, handles or paths from the user's Tokyo Nights collection.
- Connecting a kit to the streamer's existing tools (`docs/CONNECT.md`): real values go only into the
  personal collection in OBS's scenes folder; plans hold names and positions; tests use made-up data.
- Never overwrite an existing OBS scene collection; tests use `OBS Brand Kit TEST - <name>`.
- Update the docs when a decision in them changes.
