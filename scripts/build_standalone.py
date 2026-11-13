"""Build one self-contained HTML file from web/ that opens by double-click (no server needed).

Why: browsers block a page opened from disk (file://) from reading its data files with fetch(), and they
"taint" canvases that draw images from disk, so web/index.html shows no data and the globe throws errors.
This script puts every file the page needs inside one HTML file:
  - web/data/**/*.json  -> embedded; fetch("data/...") is answered from the embedded copy
  - web/assets/*        -> embedded as data: URLs (same origin, so canvases are not tainted)

The normal web/ folder is unchanged and is still what you host (GitHub Pages, serve.py).
"Plan your own mission" still needs python scripts/serve.py, because it runs the Python pipeline.

Usage (from the repo root):
  python scripts/build_standalone.py                       -> web_standalone/lunarwindow_standalone.html
  python scripts/build_standalone.py --out demo.html
Re-run it whenever web/index.html, web/data or web/assets change.
"""
import argparse
import base64
import json
import mimetypes
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

SHIM = """<script>
/* standalone build: data files are embedded, so the page works when opened from disk */
window.__EMBEDDED__ = __DATA__;
(function () {
  const realFetch = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const method = ((init && init.method) || "GET").toUpperCase();
    const key = url.replace(/^\\.\\//, "").split("?")[0];
    if (method === "GET" && Object.prototype.hasOwnProperty.call(window.__EMBEDDED__, key)) {
      return Promise.resolve(new Response(window.__EMBEDDED__[key], { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    if (!realFetch) return Promise.reject(new Error("fetch is not available"));
    return realFetch(input, init).catch(function (e) {
      if (method !== "GET") throw new Error("This copy runs without the server: start python scripts/serve.py for Plan your own mission");
      throw e;
    });
  };
})();
</script>"""


def data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default=str(WEB), help="the web/ folder")
    ap.add_argument("--out", default=str(ROOT / "web_standalone" / "lunarwindow_standalone.html"))
    a = ap.parse_args()
    web = Path(a.web)
    html = (web / "index.html").read_text(encoding="utf-8")

    # 1. data files, keyed by the path the page fetches ("data/results.json", "data/sites/210.json", ...)
    data = {}
    for f in sorted((web / "data").rglob("*.json")):
        text = f.read_text(encoding="utf-8")
        json.loads(text)                               # stop early on a broken file
        data[f.relative_to(web).as_posix()] = text
    if "data/results.json" not in data:
        sys.exit("web/data/results.json is missing")

    # 2. images: replace every "assets/<file>" string in the page with a data: URL
    used = 0
    for f in sorted((web / "assets").glob("*")):
        ref = f"assets/{f.name}"
        if ref in html:
            html = html.replace(f'"{ref}"', f'"{data_url(f)}"').replace(f"'{ref}'", f"'{data_url(f)}'")
            used += 1
    left = re.findall(r"""["'`]assets/[^"'`]+["'`]""", html)
    if left:
        sys.exit(f"these asset references could not be embedded: {left}")

    # 3. the fetch shim goes first in <head>, before the page's own scripts run
    shim = SHIM.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    if "<head>" not in html:
        sys.exit("index.html has no <head> tag")
    html = html.replace("<head>", "<head>\n" + shim, 1)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB): {len(data)} data files, {used} images embedded.")
    print("Open it by double-click. Plan your own mission still needs: python scripts/serve.py")


if __name__ == "__main__":
    main()
