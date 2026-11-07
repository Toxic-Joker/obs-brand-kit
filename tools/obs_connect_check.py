"""Open OBS on a collection that's already in the scenes folder, check it, screenshot it, put OBS back.

  python tools/obs_connect_check.py "<collection name>" --out <dir>

Run with plain `python` (not -I): needs the `websockets` package from the user site-packages.
OBS must be closed. Reuses tools/verify_obs.py (websocket client + scene inspection).
Afterwards: OBS switched back to the collection that was active, user.ini and Aitum's config restored,
every other collection file hash-identical (checked), and the user.ini backup deleted (it holds tokens).
"""
import argparse, asyncio, configparser, hashlib, json, os, shutil, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("--out", required=True)
a = ap.parse_args()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_obs as V  # noqa: E402

MAIN_CANVAS = "6c69626f-6273-4c00-9d88-c5136d61696e"
os.makedirs(a.out, exist_ok=True)
if subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True).stdout.count("obs64.exe"):
    sys.exit("Close OBS first.")
path = None
for f in os.listdir(V.SCENES):
    if f.endswith(".json"):
        try:
            if json.load(open(os.path.join(V.SCENES, f), encoding="utf-8")).get("name") == a.name:
                path = os.path.join(V.SCENES, f)
        except Exception: pass
if not path: sys.exit(f"{a.name!r} is not in {V.SCENES}")
coll = json.load(open(path, encoding="utf-8"))
digest = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
others = {f: digest(os.path.join(V.SCENES, f)) for f in os.listdir(V.SCENES)
          if f.endswith(".json") and os.path.join(V.SCENES, f) != path}

ini_bak = os.path.join(a.out, "user.ini.bak")
shutil.copy2(V.USER_INI, ini_bak)
aitum_cfg = os.path.join(V.APPDATA, "obs-studio", "plugin_config", "vertical-canvas", "config.json")
aitum_bak = os.path.join(a.out, "vertical-canvas.config.bak")  # holds stream keys: copied byte for byte, never read
if os.path.exists(aitum_cfg): shutil.copy2(aitum_cfg, aitum_bak)
ini = configparser.ConfigParser(strict=False, interpolation=None); ini.read(V.USER_INI, encoding="utf-8-sig")
prev = ini["Basic"]["SceneCollection"]
ws_cfg = json.load(open(os.path.join(V.APPDATA, "obs-studio", "plugin_config", "obs-websocket", "config.json")))
port, pw = ws_cfg["server_port"], ws_cfg.get("server_password", "")

async def devices():
    rep = {}
    async with V.WS(port, pw) as ws:
        for i in (await ws.req("GetInputList"))["inputs"]:
            n, k = i["inputName"], i["inputKind"]
            if k in ("dshow_input", "wasapi_input_capture", "wasapi_output_capture", "wasapi_process_output_capture"):
                m = await ws.req("GetInputMute", {"inputName": n}); v = await ws.req("GetInputVolume", {"inputName": n})
                rep[n] = {"kind": k, "muted": m["inputMuted"], "vol": round(v["inputVolumeMul"], 3)}
            if k == "browser_source":
                st = (await ws.req("GetInputSettings", {"inputName": n}))["inputSettings"]
                rep[n] = {"kind": k, "url_set": st.get("url", "").startswith("http")}
    return rep

proc = subprocess.Popen([os.path.join(V.OBS_DIR, "obs64.exe"), "--collection", a.name, "--disable-shutdown-check",
                         "--disable-updater"], cwd=V.OBS_DIR)
report = {}
try:
    time.sleep(8)
    report["inputs"] = asyncio.run(devices())
    vscenes = {x["name"]: x["uuid"] for x in coll["sources"]
               if x["id"] == "scene" and (x.get("canvas_uuid") or MAIN_CANVAS) != MAIN_CANVAS}
    report.update(asyncio.run(V.inspect(port, pw, a.name, prev, a.out, vscenes)))
except BaseException:
    try:
        async def back():
            async with V.WS(port, pw) as ws:
                await ws.req("SetCurrentSceneCollection", {"sceneCollectionName": prev})
        asyncio.run(back())
    except Exception as e:
        print(f"could not switch OBS back to {prev!r}: {e}")
    raise
finally:
    for _ in range(3):
        subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True)
        for _ in range(20):
            if proc.poll() is not None: break
            time.sleep(1)
        if proc.poll() is not None: break
    if proc.poll() is None:
        print(f"WARNING: OBS (PID {proc.pid}) is still open. Switch it to {prev!r} and close it yourself.")
    else:
        shutil.copy2(ini_bak, V.USER_INI)
        if os.path.exists(aitum_bak): shutil.copy2(aitum_bak, aitum_cfg)
    for p in (ini_bak, aitum_bak):
        if os.path.exists(p) and proc.poll() is not None: os.remove(p)

changed = [f for f, h in others.items() if not os.path.exists(os.path.join(V.SCENES, f)) or digest(os.path.join(V.SCENES, f)) != h]
report["other_collections_unchanged"] = not changed
if changed: report["CHANGED"] = changed
json.dump(report, open(os.path.join(a.out, "report.json"), "w"), indent=1)
print(json.dumps({k: report.get(k) for k in ("collection", "restored_to", "other_collections_unchanged", "CHANGED", "transition", "inputs")}, indent=1))
print("missing media:", [n for n, m in report.get("media", {}).items() if not m["exists"]])
print("vertical:", json.dumps(report.get("vertical", {}).get("linked")))
print("screenshots:", a.out)
