"""python -m kit build brands/<slug> [--skip-render] [--only a,b]"""
import argparse, json, os, shutil, sys, time

from . import brand as brandmod, ec
from .assets import ASSETS, VERTICAL_ASSETS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class Work:
    def __init__(self, slug):
        self.dist = os.path.join(ROOT, "dist", slug)
        self.assets = os.path.join(self.dist, "assets")
        self.projects = os.path.join(ROOT, "build", slug, "projects")  # editable EffectCraft projects
        os.makedirs(self.assets, exist_ok=True); os.makedirs(self.projects, exist_ok=True)
    def proj(self, name): return os.path.join(self.projects, name + ".ecproj")
    def out(self, file): return os.path.join(self.assets, file)

def render(b, work, only=None):
    manifest_path = os.path.join(work.dist, "assets.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) and only else {}
    for key, fn in ASSETS.items():
        if only and key not in only:
            continue
        if key in VERTICAL_ASSETS and not b["vertical"]:
            manifest.pop(key, None)
            continue
        t = time.time()
        manifest[key] = fn(b, work)
        print(f"  {key:<16} {manifest[key]['file']:<24} {manifest[key]['w']}x{manifest[key]['h']}  {time.time() - t:.1f}s")
    json.dump(manifest, open(manifest_path, "w"), indent=1)
    m = os.path.join(work.projects, "_measure.ecproj")
    if os.path.exists(m):
        os.remove(m)
    return manifest

def main():
    ap = argparse.ArgumentParser(prog="python -m kit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build", help="render assets and write the OBS collection + Streamlabs overlay")
    p.add_argument("brand_dir")
    p.add_argument("--skip-render", action="store_true", help="reuse dist/<slug>/assets")
    p.add_argument("--only", help="comma-separated asset keys to re-render")
    a = ap.parse_args()

    b = brandmod.load(a.brand_dir)
    work = Work(b.slug)
    if a.skip_render:
        manifest = json.load(open(os.path.join(work.dist, "assets.json")))
    else:
        brandmod.check_fonts(b, ec.fonts())
        print(f"Rendering assets for {b.name} with {ec.find_cli()}")
        manifest = render(b, work, set(a.only.split(",")) if a.only else None)

    from . import package
    package.build(b, work, manifest)

if __name__ == "__main__":
    main()
