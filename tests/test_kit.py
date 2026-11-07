"""python -m unittest discover -s tests   (run after a build)

Besides the generic checks, this reads the reference collection on THIS PC at test time (never
stored) and asserts none of its widget tokens, URLs, handles or file paths reached the output.
"""
import glob, json, os, re, sys, unittest, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from kit import check  # noqa: E402

def reference_secrets():
    vals = set()
    for p in glob.glob(os.path.expandvars(r"%APPDATA%\obs-studio\basic\scenes\Toyko_Nights*.json")):
        d = json.load(open(p, encoding="utf-8"))
        for s in d.get("sources", []):
            st = s.get("settings", {})
            url = st.get("url", "")
            if url:
                vals.add(url)
                # keys/ids: 10+ chars that mix letters and digits
                vals.update(t for t in re.findall(r"[A-Za-z0-9_\-]{10,}", url)
                            if re.search(r"\d", t) and re.search(r"[A-Za-z]", t))
            if s.get("id", "").startswith("text") and len(st.get("text", "")) >= 5:
                vals.add(st["text"])  # the streamer's handles
    return vals

def own_values():
    """brand name -> the brand's own name / handles (lower-case, no @). A kit may show its own
    handles even when the reference collection uses them; everything else stays forbidden."""
    out = {}
    for bj in glob.glob(os.path.join(ROOT, "brands", "*", "brand.json")) + glob.glob(os.path.join(ROOT, "private", "brands", "*", "brand.json")):
        b = json.load(open(bj, encoding="utf-8"))
        vals = {b["name"], b["handle"], *(s["handle"] for s in b.get("socials", []))}
        out[b["name"]] = {v.lower().lstrip("@") for v in vals}
    return out

def forbidden_for(path, forbidden, owners):
    """Forbidden values minus the brand's own handles; the brand is found from the file name."""
    base = os.path.basename(path)
    own = next((v for name, v in owners.items() if base.startswith(name + " Brand Kit")), set())
    return {f for f in forbidden if f.lower().lstrip("@") not in own}

class KitOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.colls = glob.glob(os.path.join(ROOT, "dist", "*", "*Brand Kit.json"))
        cls.overlays = glob.glob(os.path.join(ROOT, "dist", "*.overlay"))
        if not cls.colls:
            raise unittest.SkipTest("build a brand first: python -m kit build brands/<slug>")
        cls.forbidden = reference_secrets()
        cls.owners = own_values()

    def test_obs_collection(self):
        for p in self.colls:
            coll = json.load(open(p, encoding="utf-8"))
            self.assertEqual(check.check_obs(coll, os.path.dirname(p), forbidden_for(p, self.forbidden, self.owners)), [], p)

    def test_overlay(self):
        for p in self.overlays:
            self.assertEqual(check.check_overlay(p, forbidden_for(p, self.forbidden, self.owners)), [], p)

    def test_placeholders_everywhere(self):
        for p in self.colls:
            coll = json.load(open(p, encoding="utf-8"))
            urls = [s["settings"]["url"] for s in coll["sources"] if s["id"] == "browser_source"]
            self.assertTrue(urls)
            self.assertTrue(all(re.fullmatch(r"about:blank#PASTE_YOUR_[A-Z_]+_URL", u) for u in urls), urls)

    def test_no_reference_value_in_any_shipped_file(self):
        """Raw byte scan of every text file in the zips/overlays."""
        for z in glob.glob(os.path.join(ROOT, "dist", "*.zip")) + self.overlays:
            with zipfile.ZipFile(z) as zf:
                for n in zf.namelist():
                    if n.endswith((".json", ".md")):
                        text = zf.read(n).decode("utf-8")
                        for v in forbidden_for(z, self.forbidden, self.owners):
                            self.assertNotIn(v, text, f"{z}:{n}")

    def test_vertical_canvas(self):
        """Vertical scenes live on the "Aitum Vertical" canvas, never in the main scene list, and every
        horizontal scene links to its (V) twin; the horizontal-only copy has none of it."""
        for p in self.colls:
            coll = json.load(open(p, encoding="utf-8"))
            if "canvases" not in coll:
                continue
            (canvas,) = coll["canvases"]
            self.assertEqual(canvas["info"]["name"], "Aitum Vertical")
            vs = [s for s in coll["sources"] if s.get("canvas_uuid")]
            self.assertTrue(vs)
            self.assertTrue(all(s["canvas_uuid"] == canvas["info"]["uuid"] for s in vs))
            order = {x["name"] for x in coll["scene_order"]}
            self.assertFalse(order & {s["name"] for s in vs})
            vnames = {s["name"] for s in vs}
            want = coll["name"].replace(" Brand Kit", "") + " Stinger (V)"
            self.assertTrue(all(s["private_settings"].get("transition") == want for s in vs))
            kit = os.path.dirname(p)
            ps1 = open(os.path.join(kit, "Add vertical stinger.ps1"), encoding="utf-8-sig").read()
            self.assertIn(f'$Name  = "{want}"', ps1)
            self.assertTrue(os.path.exists(os.path.join(kit, "Add vertical stinger.cmd")))
            for s in coll["sources"]:
                for link in s["settings"].get("canvas", []) if s["id"] == "scene" else []:
                    self.assertIn(link["scene"], vnames)
            h = p.replace(".json", " (horizontal only).json")
            hc = json.load(open(h, encoding="utf-8"))
            self.assertNotIn("canvases", hc)
            self.assertFalse(any(s.get("canvas_uuid") or s["settings"].get("canvas") for s in hc["sources"]))
            self.assertEqual(check.check_obs(hc, os.path.dirname(h), forbidden_for(h, self.forbidden, self.owners)), [])

    def test_relative_coordinates(self):
        """Every item carries OBS 31+ relative coordinates for its own canvas. Without them a plugin
        canvas (no video at load time) puts every item nowhere and the scene renders black."""
        for p in self.colls:
            coll = json.load(open(p, encoding="utf-8"))
            for s in coll["sources"]:
                if s["id"] != "scene":
                    continue
                ref = [1080.0, 1920.0] if s.get("canvas_uuid") else [float(coll["resolution"]["x"]), float(coll["resolution"]["y"])]
                for it in s["settings"]["items"]:
                    self.assertEqual([it["scale_ref"]["x"], it["scale_ref"]["y"]], ref, (s["name"], it["name"]))
                    for k in ("pos_rel", "scale_rel", "bounds_rel"):
                        self.assertIn(k, it, (s["name"], it["name"]))
                    X, Y = ref
                    self.assertAlmostEqual(it["pos_rel"]["x"], (2 * it["pos"]["x"] - X) / Y, places=6)
                    self.assertAlmostEqual(it["pos_rel"]["y"], 2 * it["pos"]["y"] / Y - 1, places=6)

if __name__ == "__main__":
    unittest.main()
