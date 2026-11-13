import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _web(tmp_path, results=True):
    web = tmp_path / "web"
    (web / "data" / "sites").mkdir(parents=True)
    (web / "assets").mkdir()
    (web / "index.html").write_text('<html><head><title>t</title></head><body>'
                                    '<script>const IMG = "assets/dot.png";</script></body></html>')
    (web / "assets" / "dot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    if results:
        (web / "data" / "results.json").write_text(json.dumps({"meta": {"version": 4}}))
    (web / "data" / "sites" / "1.json").write_text("{}")
    return web


def _build(web, out):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "build_standalone.py"), "--web", str(web),
                           "--out", str(out)], capture_output=True, text=True)


def test_one_file_holds_the_data_under_the_paths_the_page_fetches_and_the_images(tmp_path):
    out = tmp_path / "one.html"
    assert _build(_web(tmp_path), out).returncode == 0
    html = out.read_text(encoding="utf-8")
    assert '"data/results.json"' in html and '"data/sites/1.json"' in html
    assert '"data:image/png;base64,' in html and '"assets/dot.png"' not in html
    assert html.index("window.__EMBEDDED__") < html.index("const IMG")       # the shim runs before the page


def test_no_results_no_build(tmp_path):
    run = _build(_web(tmp_path, results=False), tmp_path / "one.html")
    assert run.returncode != 0 and "results.json is missing" in run.stderr
