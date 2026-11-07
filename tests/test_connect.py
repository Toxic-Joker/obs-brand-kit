"""Tests for tools/obs_connect.py + tools/obs_inventory.py on made-up data only (run after a build).

A fake "existing" collection (fake URL, fake camera) goes into a temporary OBS folder (APPDATA points
there), so nothing of the real OBS install is read or written.
"""
import glob, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
FAKE_URL = "https://example.invalid/alert-box/v3/FAKE0token0123456789"
def wj(path, obj):
    with open(path, "w", encoding="utf-8") as f: json.dump(obj, f)

def rj(path):
    with open(path, encoding="utf-8") as f: return json.load(f)

def wt(path, text):
    with open(path, "w", encoding="utf-8") as f: f.write(text)

MAIN = "6c69626f-6273-4c00-9d88-c5136d61696e"

def kit_json():
    for p in sorted(glob.glob(os.path.join(ROOT, "dist", "*", "* Brand Kit.json"))):
        if "(horizontal only)" not in p: return p
    return None

def source(name, id_, settings, **extra):
    return {"name": name, "uuid": f"uuid-{name}", "id": id_, "versioned_id": id_, "settings": settings,
            "volume": 0.5, "muted": False, "monitoring_type": 2, "filters": [], **extra}

def item(name, visible=True):
    return {"name": name, "visible": visible, "pos": {"x": 0, "y": 0}, "scale": {"x": 1, "y": 1}}

def fake_collection():
    srcs = [source("My Alerts", "browser_source", {"url": FAKE_URL, "width": 1920, "height": 1080}),
            source("My Cam", "dshow_input", {"video_device_id": "Fake Cam:\\\\?\\usb#fake"}),
            source("Old Goal", "browser_source", {"url": "https://example.invalid/goal/FAKE0goal0123456"})]
    srcs.append(source("Live", "scene", {"items": [item("My Alerts"), item("My Cam"), item("Old Goal", False)]}))
    return {"name": "Fake Existing", "sources": srcs, "scene_order": [{"name": "Live"}]}

@unittest.skipUnless(kit_json(), "build a brand first (python -m kit build brands/northwind)")
class Connect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scenes = os.path.join(self.tmp, "obs-studio", "basic", "scenes")
        os.makedirs(self.scenes)
        wj(os.path.join(self.scenes, "Fake_Existing.json"), fake_collection())
        self.kit = kit_json()
        kit = rj(self.kit)
        scenes = {s["name"]: s for s in kit["sources"] if s["id"] == "scene"}
        self.cam_scene = next(n for n, s in scenes.items() if (s.get("canvas_uuid") or MAIN) == MAIN
                              and any(i["name"] == "Webcam" for i in s["settings"]["items"]))
        srcs = {s["name"]: s for s in kit["sources"]}
        # a piece of the kit's own look in that scene (image or video), kept with {"kit": true}
        self.kit_item = next(i for i in scenes[self.cam_scene]["settings"]["items"]
                             if srcs.get(i["name"], {}).get("id") in ("image_source", "ffmpeg_source"))
        self.plan = {"name": "Fake Live", "file": "Fake_Live.json", "source": "Fake Existing", "kit": self.kit,
                     "assets": os.path.join(self.tmp, "assets"), "keep_kit": [self.kit_item["name"]],
                     "sources": {"Webcam": {"from": "My Cam", "set": {"muted": True}},
                                 "Alert Box": {"from": "My Alerts"}},
                     "scenes": {self.cam_scene: [["Webcam", {"x": 100, "y": 50, "box": [640, 360], "fill": True, "mirror": True}],
                                                 [self.kit_item["name"], {"kit": True}], ["[S] Alerts", {}]],
                                "[S] Alerts": [["Alert Box", {"x": 560, "y": 40, "box": [800, 450]}]]}}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, tool, *args):
        env = dict(os.environ, APPDATA=self.tmp)
        return subprocess.run([sys.executable, "-I", os.path.join(TOOLS, tool), *args],
                              capture_output=True, text=True, env=env)

    def write_plan(self, **over):
        p = os.path.join(self.tmp, "plan.json")
        wj(p, {**self.plan, **over})
        return p

    def test_build(self):
        r = self.run_tool("obs_connect.py", self.write_plan())
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        out = rj(os.path.join(self.scenes, "Fake_Live.json"))
        S = {s["name"]: s for s in out["sources"]}
        self.assertEqual(S["Alert Box"]["settings"]["url"], FAKE_URL)     # the real tool was carried over
        self.assertTrue(S["Webcam"]["muted"])
        self.assertNotIn("Old Goal", S)                                      # nothing the plan didn't ask for
        self.assertNotIn("PASTE_YOUR", json.dumps(out))                     # unused kit placeholders dropped
        self.assertFalse([k for k in out if k.startswith(("DesktopAudioDevice", "AuxAudioDevice"))])
        cam = S[self.cam_scene]["settings"]["items"][0]
        self.assertEqual((cam["pos"]["x"], cam["scale"]["x"]), (100.0, -1.0))  # bounded flip stays in its box
        self.assertAlmostEqual(cam["pos_rel"]["x"], (2 * 100 - 1920) / 1080)
        self.assertEqual(rj(os.path.join(self.tmp, "obs-studio", "obs-connect-tools.json")), ["Fake Live"])
        media = [s["settings"].get("local_file") or s["settings"].get("file") for s in out["sources"]
                 if s["id"] in ("ffmpeg_source", "image_source")]
        self.assertTrue(all(os.path.exists(m) for m in media))
        kept = S[self.cam_scene]["settings"]["items"][1]                    # {"kit": true}: kit placement as-is
        for k in ("pos", "scale", "align", "bounds_type", "bounds", "pos_rel"):
            self.assertEqual(kept.get(k), self.kit_item.get(k), k)
        self.assertTrue(kept["visible"])

    def test_refusals(self):
        r = self.run_tool("obs_connect.py", self.write_plan(file="Fake_Existing.json"), "--replace")
        self.assertIn("output = source", r.stdout + r.stderr)
        shutil.copy(os.path.join(self.scenes, "Fake_Existing.json"), os.path.join(self.scenes, "Other.json"))
        other = rj(os.path.join(self.scenes, "Other.json")); other["name"] = "Other"
        wj(os.path.join(self.scenes, "Other.json"), other)
        r = self.run_tool("obs_connect.py", self.write_plan(file="Other.json", name="Other"), "--replace")
        self.assertIn("only collections this tool made", r.stdout + r.stderr)
        r = self.run_tool("obs_connect.py", self.write_plan(assets=os.path.join(ROOT, "dist", "personal-assets")))
        self.assertIn("inside the kit repo", r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "dist", "personal-assets")))

    def test_inventory(self):
        r = self.run_tool("obs_inventory.py", "list")
        self.assertIn("Fake Existing", r.stdout)
        self.assertIn("has real devices/widgets", r.stdout)
        r = self.run_tool("obs_inventory.py", "tools", "Fake Existing")
        used = r.stdout.split("HIDDEN EVERYWHERE")[0]
        self.assertIn("My Alerts  <widget: alerts>", used)
        self.assertIn("My Cam  <device: camera>", used)
        self.assertNotIn("FAKE0token0123456789", r.stdout)                  # URLs are printed masked
        self.assertIn("Old Goal", r.stdout.split("HIDDEN EVERYWHERE")[1])

    def test_leak_scan(self):
        clean = os.path.join(self.tmp, "clean"); os.makedirs(clean)
        wt(os.path.join(clean, "a.txt"), "nothing here")
        self.assertEqual(self.run_tool("leak_scan.py", "Fake Existing", clean).returncode, 0)
        wt(os.path.join(clean, "b.txt"), "oops " + FAKE_URL)
        r = self.run_tool("leak_scan.py", "Fake Existing", clean)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("FAKE0token0123456789", r.stdout)

if __name__ == "__main__":
    unittest.main()
