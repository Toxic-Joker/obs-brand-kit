"""Load a built kit into the local OBS as a NEW collection and screenshot every scene.

  python tools/verify_obs.py "dist/northwind/Northwind Brand Kit.json" --out <dir>

1. Translates ./ paths exactly like OBS's importer (frontend/importers/studio.cpp) and writes the
   collection as "<name> (test import)". Refuses to overwrite any existing collection file.
2. Starts OBS on that collection (OBS must be closed), talks to obs-websocket (port and password
   from its config; never printed), lists scenes/inputs, checks media files load, screenshots scenes.
3. Switches OBS back to the collection that was active before, closes OBS, restores user.ini.
"""
import argparse, asyncio, base64, configparser, hashlib, json, os, shutil, subprocess, sys, time

APPDATA = os.environ["APPDATA"]
OBS_DIR = r"C:\Program Files\obs-studio\bin\64bit"
SCENES = os.path.join(APPDATA, "obs-studio", "basic", "scenes")
USER_INI = os.path.join(APPDATA, "obs-studio", "user.ini")

def translate_paths(obj, root):
    if isinstance(obj, dict):
        return {k: translate_paths(v, root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_paths(v, root) for v in obj]
    if isinstance(obj, str) and obj.startswith("./"):
        p = os.path.abspath(os.path.join(root, obj))
        return p.replace("\\", "/") if p.startswith(os.path.abspath(root) + os.sep) else obj
    return obj

class WS:
    def __init__(self, port, password):
        self.url, self.pw, self.n = f"ws://127.0.0.1:{port}", password, 0
    async def __aenter__(self):
        import websockets
        for _ in range(60):
            try:
                self.ws = await websockets.connect(self.url, max_size=64 * 2**20); break
            except OSError:
                await asyncio.sleep(1)
        else:
            sys.exit("obs-websocket did not come up")
        hello = json.loads(await self.ws.recv())["d"]
        ident = {"rpcVersion": 1}
        if "authentication" in hello:
            a = hello["authentication"]
            secret = base64.b64encode(hashlib.sha256((self.pw + a["salt"]).encode()).digest()).decode()
            ident["authentication"] = base64.b64encode(hashlib.sha256((secret + a["challenge"]).encode()).digest()).decode()
        await self.ws.send(json.dumps({"op": 1, "d": ident}))
        json.loads(await self.ws.recv())
        return self
    async def __aexit__(self, *a):
        await self.ws.close()
    async def req(self, rtype, data=None):
        for _ in range(60):  # 207 = OBS still starting up
            try:
                return await self._req(rtype, data)
            except RuntimeError as e:
                if "'code': 207" not in str(e):
                    raise
                await asyncio.sleep(1)
        raise RuntimeError(f"{rtype}: OBS never became ready")
    async def _req(self, rtype, data=None):
        self.n += 1
        await self.ws.send(json.dumps({"op": 6, "d": {"requestType": rtype, "requestId": str(self.n), "requestData": data or {}}}))
        while True:
            m = json.loads(await self.ws.recv())
            if m["op"] == 7 and m["d"]["requestId"] == str(self.n):
                st = m["d"]["requestStatus"]
                if not st["result"]:
                    raise RuntimeError(f"{rtype}: {st}")
                return m["d"].get("responseData", {})

async def inspect(port, pw, name, prev, out, vscenes=None):
    report = {}
    async with WS(port, pw) as ws:
        cur = (await ws.req("GetSceneCollectionList"))["currentSceneCollectionName"]
        report["collection"] = cur
        assert cur == name, f"OBS opened {cur!r}, expected {name!r}"
        scenes = [s["sceneName"] for s in reversed((await ws.req("GetSceneList"))["scenes"])]
        report["scenes"] = {}
        for s in scenes:
            items = (await ws.req("GetSceneItemList", {"sceneName": s}))["sceneItems"]
            report["scenes"][s] = [(i["sourceName"], i["inputKind"] or "scene", i["sceneItemEnabled"]) for i in items]
        inputs = (await ws.req("GetInputList"))["inputs"]
        report["media"] = {}
        for i in inputs:
            if i["inputKind"] in ("ffmpeg_source", "image_source"):
                st = (await ws.req("GetInputSettings", {"inputName": i["inputName"]}))["inputSettings"]
                f = st.get("local_file") or st.get("file")
                report["media"][i["inputName"]] = {"exists": os.path.exists(f)}
        tr = await ws.req("GetCurrentSceneTransition")
        report["transition"] = {"name": tr["transitionName"], "kind": tr["transitionKind"],
                                "file_exists": os.path.exists(tr["transitionSettings"].get("path", ""))}
        for s in scenes:
            await ws.req("SetCurrentProgramScene", {"sceneName": s})
        for s in scenes:
            await ws.req("SetCurrentProgramScene", {"sceneName": s})
            await asyncio.sleep(2.5)  # let media start (stinger plays between scenes)
            shot = await ws.req("GetSourceScreenshot", {"sourceName": s, "imageFormat": "png", "imageWidth": 960})
            with open(os.path.join(out, f"scene_{s.replace(' ', '_').replace('[', '').replace(']', '')}.png"), "wb") as f:
                f.write(base64.b64decode(shot["imageData"].split(",", 1)[1]))
        if vscenes:
            report["vertical"] = await check_vertical(ws, scenes, vscenes, out)
        await ws.req("SetCurrentSceneCollection", {"sceneCollectionName": prev})
        await asyncio.sleep(3)
        report["restored_to"] = (await ws.req("GetSceneCollectionList"))["currentSceneCollectionName"]
    return report

async def check_vertical(ws, main_scenes, vscenes, out):
    """vscenes: {name: uuid} of the scenes on the vertical canvas. Read-only vendor calls plus
    switch_scene; nothing that streams or records."""
    rep = {"in_main_list": [s for s in main_scenes if s in vscenes]}
    async def vendor(req, data=None):
        r = await ws.req("CallVendorRequest", {"vendorName": "aitum-vertical-canvas", "requestType": req,
                                                "requestData": data or {}})
        return r.get("responseData", {})
    try:
        rep["plugin_scenes"] = [x["name"] for x in (await vendor("get_scenes")).get("scenes", [])]
    except RuntimeError as e:
        rep["plugin"] = f"not available ({e})"
        return rep
    # linked switching: horizontal scene -> its (V) twin
    links = {}
    for h in main_scenes:
        if h + " (V)" in vscenes:
            await ws.req("SetCurrentProgramScene", {"sceneName": h})
            await asyncio.sleep(2)
            links[h] = (await vendor("current_scene")).get("scene")
    rep["linked"] = links
    for v, uuid in vscenes.items():
        await vendor("switch_scene", {"scene": v})
        await asyncio.sleep(2.5)
        shot = await ws.req("GetSourceScreenshot", {"sourceUuid": uuid, "imageFormat": "png", "imageWidth": 540})
        with open(os.path.join(out, f"vscene_{v.replace(' ', '_').replace('(', '').replace(')', '')}.png"), "wb") as f:
            f.write(base64.b64decode(shot["imageData"].split(",", 1)[1]))
    return rep

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("collection_json"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True).stdout.count("obs64.exe"):
        sys.exit("Close OBS first.")

    src = os.path.abspath(a.collection_json)
    coll = translate_paths(json.load(open(src, encoding="utf-8")), os.path.dirname(src))
    name = coll["name"] + " (test import)"
    coll["name"] = name
    target = os.path.join(SCENES, name.replace(" ", "_").replace("(", "").replace(")", "") + ".json")
    if os.path.exists(target):
        sys.exit(f"{target} already exists; not overwriting. Remove it yourself if it's an old test.")
    shutil.copy2(USER_INI, os.path.join(a.out, "user.ini.bak"))
    # Aitum Vertical keeps its current scene in its own settings (next to the user's stream keys):
    # copy the file byte for byte and put it back after OBS closes. Never parsed or printed.
    aitum_cfg = os.path.join(APPDATA, "obs-studio", "plugin_config", "vertical-canvas", "config.json")
    aitum_bak = os.path.join(a.out, "vertical-canvas.config.bak")
    if os.path.exists(aitum_cfg):
        shutil.copy2(aitum_cfg, aitum_bak)
    ini = configparser.ConfigParser(strict=False, interpolation=None)
    ini.read(USER_INI, encoding="utf-8-sig")
    prev = ini["Basic"]["SceneCollection"]
    ws_cfg = json.load(open(os.path.join(APPDATA, "obs-studio", "plugin_config", "obs-websocket", "config.json")))
    with open(target, "w", encoding="utf-8") as f:
        json.dump(coll, f, indent=2, ensure_ascii=False)

    proc = subprocess.Popen([os.path.join(OBS_DIR, "obs64.exe"), "--collection", name, "--disable-shutdown-check",
                             "--disable-updater"], cwd=OBS_DIR)
    port, pw = ws_cfg["server_port"], ws_cfg.get("server_password", "")
    try:
        vscenes = {x["name"]: x["uuid"] for x in coll["sources"] if x.get("canvas_uuid")}
        report = asyncio.run(inspect(port, pw, name, prev, a.out, vscenes))
    except BaseException:
        try:  # leave OBS on the user's collection even when the check fails
            async def back():
                async with WS(port, pw) as ws:
                    await ws.req("SetCurrentSceneCollection", {"sceneCollectionName": prev})
            asyncio.run(back())
        except Exception as e:
            print(f"could not switch OBS back to {prev!r}: {e}")
        raise
    finally:
        for _ in range(3):  # gentle close (WM_CLOSE); OBS ignores it while still loading
            subprocess.run(["taskkill", "/PID", str(proc.pid)], capture_output=True)
            for _ in range(20):
                if proc.poll() is not None: break
                time.sleep(1)
            if proc.poll() is not None: break
        if proc.poll() is None:
            print(f"WARNING: OBS (PID {proc.pid}) is still open. Switch it to {prev!r} and close it yourself.")
        else:
            shutil.copy2(os.path.join(a.out, "user.ini.bak"), USER_INI)
            if os.path.exists(aitum_bak):
                shutil.copy2(aitum_bak, aitum_cfg)
                os.remove(aitum_bak)  # holds stream keys: don't leave a copy in the output folder
    json.dump(report, open(os.path.join(a.out, "report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
    print("test collection left in OBS as:", name)

if __name__ == "__main__":
    main()
