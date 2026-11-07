"""Check that no real widget token from the user's collection sits in shareable or working folders.

  python tools/leak_scan.py "<source collection>" <folder> [<folder> ...]

Prints the files that contain a token-like fragment (12+ chars) from any browser-source URL of the source
collection, with the fragment masked and its surrounding text, so a plain word ("StreamElements") can be
told apart from a real token. Exit code 1 when anything matched.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from obs_inventory import load  # noqa: E402

if len(sys.argv) < 3: sys.exit(__doc__)
_, d = load(sys.argv[1])
needles = {}
for s in d["sources"]:
    for tok in re.findall(r"[A-Za-z0-9_\-]{12,}", s["settings"].get("url", "")):
        if not re.fullmatch(r"[a-z\-]+|[a-z]*([A-Z][a-z]+)+", tok): needles[tok] = s["name"]  # skip plain/CamelCase words
hits = 0
for root in sys.argv[2:]:
    for dp, _, fs in os.walk(root):
        for f in fs:
            fp = os.path.join(dp, f)
            try: t = open(fp, "rb").read().decode("utf-8", "replace")
            except OSError: continue
            for n, src in needles.items():
                i = t.find(n)
                if i >= 0:
                    hits += 1
                    shape = re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", n)))
                    ctx = t[max(0, i - 40):i + len(n) + 15].replace(n, "<<TOKEN>>").replace("\n", " ")
                    print(f"{fp}\n   from {src!r}, shape {shape}: …{ctx}…")
                    break
print(f"{len(needles)} fragments checked, {hits} file(s) matched")
sys.exit(1 if hits else 0)
