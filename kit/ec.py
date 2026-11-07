"""EffectCraft driver: build a comp layer by layer through effectcraft-cli, then render it.

Trimmed from our CTA pipeline (~/Videos/FilmCraft/CTA/build_ctas.py). All motion is expressions,
so a comp is fully described by code and re-renders for any brand.
"""
import array, glob, json, math, os, random, re, subprocess, sys, time, wave

def find_cli():
    """Newest installed EffectCraft (the Artcraft updater renames the version folder)."""
    if os.environ.get("EFFECTCRAFT_CLI"):
        return os.environ["EFFECTCRAFT_CLI"]
    pat = os.path.expanduser(r"~\Documents\Claude\Artcraft\effectcraft\app\effectcraft-*-portable\effectcraft-cli.exe")
    found = glob.glob(pat)
    ver = lambda p: [int(x) for x in re.search(r"effectcraft-(\d+)\.(\d+)\.(\d+)", p).groups()]
    if not found:
        sys.exit("EffectCraft CLI not found. Set EFFECTCRAFT_CLI to effectcraft-cli.exe.")
    return max(found, key=ver)

EC = None
FPS = 30

# Expression helpers (JS). `time` is seconds.
LIB = (
    "function eo(t,t0,d){var x=Math.min(1,Math.max(0,(t-t0)/d));return 1-Math.pow(1-x,3);}"
    "function eio(t,t0,d){var x=Math.min(1,Math.max(0,(t-t0)/d));return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;}"
    "function ramp(t,t0,d){return Math.min(1,Math.max(0,(t-t0)/d));}"
    "function loop(t,p){return Math.sin(2*Math.PI*t/p);};"
)

def svg(w, h, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">{body}</svg>'

def _run(args):
    global EC
    EC = EC or find_cli()
    for attempt in range(8):  # Windows can briefly lock the project file (os error 32)
        r = subprocess.run([EC, *args], capture_output=True, text=True, encoding="utf-8")
        if not (r.returncode and "os error 32" in (r.stdout + r.stderr)):
            break
        time.sleep(0.4 * (attempt + 1))
    if r.returncode:
        sys.exit(f"effectcraft-cli failed: {' '.join(args)[:300]}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r.stdout

def fonts():
    out = _run(["--empty", "run", "text.fonts", "{}"])
    j = json.loads(out[out.index("{"):])
    fams = j.get("families") or j.get("result", {}).get("families") or []
    return {f["family"] for f in fams}

class Comp:
    """One composition in its own .ecproj. Steps are queued and sent in one CLI call per flush."""
    def __init__(self, name, w, h, dur, project, fps=FPS):
        self.name, self.w, self.h, self.dur, self.proj = name, w, h, dur, project
        os.makedirs(os.path.dirname(project), exist_ok=True)
        if os.path.exists(project):
            os.remove(project)
        _run(["--empty", "--save-as", project, "run", "comp.new",
              json.dumps({"name": name, "width": w, "height": h, "frameRate": fps, "duration": dur})])

    def run(self, *pairs):
        args = []
        for cmd, p in pairs:
            args += [cmd, json.dumps(p)]
        return _run(["--project", self.proj, "--save", "run", *args])

    @staticmethod
    def _layer_id(out):
        i = out.rfind('"layer"')
        return int(out[i:].split(":")[1].split("}")[0].split(",")[0])

    def _finish(self, layer, anchor=None, pos=None, exprs=None):
        pairs = []
        if anchor is not None:
            pairs.append(("prop.set", {"layer": layer, "path": "transform/anchor", "value": [*anchor, 0]}))
        if pos is not None:
            pairs.append(("prop.set", {"layer": layer, "path": "transform/position", "value": [*pos, 0]}))
        for path, e in (exprs or {}).items():
            pairs.append(("prop.setExpression", {"layer": layer, "path": path, "expression": e}))
        if pairs:
            self.run(*pairs)
        return layer

    def shape(self, name, s, anchor, pos, exprs=None):
        """Paste an SVG as a shape layer. anchor is in SVG units, pos in comp pixels."""
        out = self.run(("edit.pasteSvg", {"svg": s, "name": name, "comp": self.name}))
        return self._finish(self._layer_id(out), anchor, pos, exprs)

    def text(self, name, text, pos, size, font, fill, style="Bold", justify="center", tracking=0, exprs=None,
             outline=None, outline_w=0):
        """pos is the baseline point (x is the centre when justify=center). outline: stroke colour drawn
        behind the fill with round joins."""
        p = {"text": text, "name": name, "font": font, "style": style, "size": size, "fill": fill, "tracking": tracking}
        if outline:
            p.update({"stroke": outline, "applyStroke": True, "strokeWidth": outline_w, "strokeOverFill": False,
                      "lineJoin": "round"})
        out = self.run(("layer.newText", p))
        layer = self._layer_id(out)
        self.run(("layer.setText", {"layer": layer, "justify": justify}))
        return self._finish(layer, None, pos, exprs)

    def image(self, name, path, pos, width, exprs=None):
        """Import a PNG and scale it to `width` px. Scale expressions return a 0..1 factor in `k`."""
        import struct
        with open(path, "rb") as f:
            native_w = struct.unpack(">I", f.read(24)[16:20])[0]
        out = self.run(("file.import", {"paths": [os.path.abspath(path)]}))
        item = json.loads(out[out.index("{"):])["items"][0]
        out = self.run(("layer.addItem", {"item": item, "position": list(pos)}))
        layer = self._layer_id(out)
        base = width / native_w * 100
        e = dict(exprs or {})
        e["transform/scale"] = LIB + e.get("transform/scale", "var k=1") + f";[k*{base},k*{base},100]"
        return self._finish(layer, None, pos, e)

    def text_widths(self, names):
        """Measured widths (px) of text layers by name."""
        js = ("var c=app.project.activeItem||app.project.item(1);var o={};"
              + "".join(f"o[{json.dumps(n)}]=c.layer({json.dumps(n)}).sourceRectAtTime(0,false).width;" for n in names)
              + "writeLn(JSON.stringify(o));")
        out = _run(["script", "--eval", js, self.proj])
        line = [l for l in out.splitlines() if l.startswith("{")][-1]
        return json.loads(line)

    def render_video(self, out_file, alpha):
        """WebM VP9 (alpha when asked). Rendered to a ProRes intermediate, then encoded by ffmpeg so
        the alpha channel and the loop length are exact."""
        tmp = out_file + ".tmp.mov"
        _run(["--project", self.proj, "render", "--comp", self.name, "--out", tmp, "--format", "prores",
              "--prores", "4444", "--channels", "rgba" if alpha else "rgb", "--audio", "off"])
        return tmp

    def still(self, t, out_png, transparent=True):
        args = ["--project", self.proj, "render-frame", "--comp", self.name, "--time", str(t), "--out", out_png]
        if transparent:
            args.append("--transparent")
        _run(args)

# ---------------------------------------------------------------- tiny synth for the stinger whoosh
SR = 48000

class Sfx:
    def __init__(self, dur, seed=7):
        self.n = int(SR * dur); self.L = [0.0] * self.n; self.R = [0.0] * self.n
        self.rnd = random.Random(seed)

    def put(self, t0, samples, gain=1.0, pan=0.0):
        s = int(t0 * SR)
        gl, gr = gain * math.cos((pan + 1) * math.pi / 4), gain * math.sin((pan + 1) * math.pi / 4)
        for i, v in enumerate(samples):
            j = s + i
            if 0 <= j < self.n:
                self.L[j] += v * gl; self.R[j] += v * gr

    def whoosh(self, d, up=True):
        n = int(d * SR); out = []; lp = bp = 0.0
        for i in range(n):
            x = i / n; k = 0.02 + 0.2 * (x if up else 1 - x)
            lp += k * (self.rnd.uniform(-1, 1) - lp); bp += k * (lp - bp)
            out.append((lp - bp) * math.sin(math.pi * x) ** 2 * 3)
        return out

    def write(self, path, peak_db=-9.0):
        peak = max(max(map(abs, self.L)), max(map(abs, self.R))) or 1
        g = 10 ** (peak_db / 20) / peak; a = array.array("h")
        for l, r in zip(self.L, self.R):
            a.append(int(l * g * 32767)); a.append(int(r * g * 32767))
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a.tobytes())

def encode_webm(src_mov, out_webm, alpha, audio_wav=None, crf=32):
    """VP9 WebM. Alpha uses yuva420p, which OBS media sources play with transparency."""
    args = ["ffmpeg", "-loglevel", "error", "-y", "-i", src_mov]
    if audio_wav:
        args += ["-i", audio_wav, "-map", "0:v", "-map", "1:a", "-c:a", "libopus", "-b:a", "96k", "-shortest"]
    args += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p" if alpha else "yuv420p", "-b:v", "0",
             "-crf", str(crf), "-row-mt", "1", "-deadline", "good", "-cpu-used", "4"]
    if alpha:
        args += ["-auto-alt-ref", "0"]
    args.append(out_webm)
    r = subprocess.run(args)
    if r.returncode:
        sys.exit(f"ffmpeg failed for {out_webm}")
    os.remove(src_mov)
