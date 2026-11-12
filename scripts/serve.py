"""Local server for the web app: serves web/ and runs hand-set missions through the real pipeline.

  GET  /...           the files in web/ (index.html, assets/, data/)
  POST /api/mission   JSON mission -> the sites/<id>.json report from scripts/analyze.py (horizon engine on LOLA,
                      NASA SPICE for the Sun and Earth, the battery model), plus the mission it ran

A mission (every field required; the page fills them from the selected site and the lander profile):
  lat, lon            degrees; the 240 m map covers 75-90 S, the 20 m map about 81.9-90 S
  terrain             "20m" (20 m map within 40 km of the site, 240 m beyond) or "240m" (240 m only)
  mast_m              panel and antenna height above the ground, 0-50 m
  start_utc           landing hour, YYYY-MM-DDTHH (UTC), 1900-2049 (the DE421 kernels)
  days                mission length, 1-60 days
  e_max_Wh, e_min_Wh  battery capacity and the reserve it must never drop below
  p_panel_W, p_load_W panel power in full Sun and the constant load
  earth_margin_deg    how far Earth must clear the skyline for contact (0 = NASA's rule: any part of the disc)

A bad mission gets HTTP 400 with the reason; the page shows it. One mission runs at a time (the engine uses every
core). The first run compiles nothing (Numba caches to disk) but loads the maps and kernels: a few seconds.

Usage:
  python scripts/serve.py                      -> http://127.0.0.1:8765/
"""
import argparse
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.analyze import analyze  # noqa: E402
from scripts.battery import Battery  # noqa: E402

FIELDS = ("lat", "lon", "terrain", "mast_m", "start_utc", "days", "e_max_Wh", "e_min_Wh", "p_panel_W", "p_load_W",
          "earth_margin_deg")


def parse_mission(body):
    """The mission as typed values; ValueError with a plain reason if a field is missing or out of range."""
    missing = [f for f in FIELDS if f not in body]
    if missing:
        raise ValueError(f"missing: {', '.join(missing)}")
    m = {f: float(body[f]) for f in FIELDS if f not in ("terrain", "start_utc")}
    m["terrain"], m["start_utc"] = str(body["terrain"]), str(body["start_utc"])
    checks = [
        (-90 <= m["lat"] <= -75, "latitude must be between 90 S and 75 S (the terrain maps are south-polar)"),
        (m["terrain"] in ("20m", "240m"), "terrain must be 20m or 240m"),
        (0 <= m["mast_m"] <= 50, "height must be 0-50 m"),
        (1 <= m["days"] <= 60, "mission length must be 1-60 days"),
        (0 <= m["e_min_Wh"] < m["e_max_Wh"], "the reserve must be at least 0 and below the battery capacity"),
        (m["p_panel_W"] >= 0 and m["p_load_W"] >= 0, "panel power and load can't be negative"),
        (0 <= m["earth_margin_deg"] <= 10, "Earth margin must be 0-10 degrees"),
    ]
    for ok, reason in checks:
        if not ok:
            raise ValueError(reason)
    t = np.datetime64(m["start_utc"], "h")                        # ValueError if malformed
    if not np.datetime64("1900-01-01T00") <= t < np.datetime64("2049-12-01T00"):
        raise ValueError("landing hour must be in 1900-2049 (the DE421 kernels)")
    m["start_utc"] = str(t)
    return m


def run_mission(m, coarse, fine, kernels):
    battery = Battery(m["e_max_Wh"], m["e_min_Wh"], m["p_panel_W"], m["p_load_W"], 1.0)
    report = analyze(m["lat"], m["lon"], m["mast_m"], m["start_utc"], m["days"], coarse,
                     fine if m["terrain"] == "20m" else None, kernels, battery, m["earth_margin_deg"], "custom")
    report["mission_inputs"] = m
    return report


class Handler(SimpleHTTPRequestHandler):
    lock = threading.Lock()
    maps = None                                                    # (coarse, fine, kernels), set in main

    def do_POST(self):
        if self.path != "/api/mission":
            return self.send_error(404)
        try:
            m = parse_mission(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            with self.lock:
                report = run_mission(m, *self.maps)
            self._json(200, report)
        except ValueError as err:                                  # bad input, or terrain that doesn't reach the site
            self._json(400, {"error": str(err)})

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--web", default=str(ROOT / "web"))
    ap.add_argument("--coarse", default=str(ROOT / "data/ldem_75s_240m.lbl"))
    ap.add_argument("--fine", default=str(ROOT / "data/ldem_80s_20m.lbl"))
    ap.add_argument("--kernels", default=str(ROOT / "data/kernels"))
    a = ap.parse_args()
    for f in (a.coarse, a.fine, a.web + "/index.html"):
        if not Path(f).exists():
            raise SystemExit(f"missing {f}")
    Handler.maps = (a.coarse, a.fine, a.kernels)
    server = ThreadingHTTPServer(("127.0.0.1", a.port), partial(Handler, directory=a.web))
    print(f"LunarWindow on http://127.0.0.1:{a.port}/  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
