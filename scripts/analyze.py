"""Any site, any landing time (official objectives 1-3, finding I): one call from coordinates to the full report.

  analyze(lat, lon, mast, start, days, coarse, fine) -> the dict scripts/score_sites.py writes to sites/<id>.json
                                                        (scripts/site_report.py; schema in docs/ui-data-contract.md)

It runs the horizon engine on the LOLA maps (the 20 m map within 40 km of the site when given, the 240 m map
beyond) and NASA SPICE for the Sun and Earth, so it needs those files and takes seconds, not milliseconds: serve it
from a local machine, and precompute the curated sites. With no fine map the skyline comes from the 240 m map
alone, which smooths away crests near the site (the Shackleton rim site looks lit on 240 m and is dark on 20 m).
Rays that leave the map are flagged in the report, not hidden.

Usage:
  python scripts/analyze.py --lat -89.778601 --lon -155.72556 --mast 2 --start 2027-03-01T06 --days 14 \
      --coarse data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --out out/analyze/rim.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon import D_FINE, D_MAX, KAPPA, N_AZ  # noqa: E402
from horizon.dem import latlon_to_xy, read_polar_dem  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.terrain import fine_bounds, multires, single  # noqa: E402
from scripts.battery import Battery  # noqa: E402
from scripts.make_sky import load_kernels, make_sky  # noqa: E402
from scripts.named_to_sites import height_and_slope  # noqa: E402
from scripts.site_report import site_report  # noqa: E402


def analyze(lat, lon, mast, start, days, coarse, fine=None, kernels="data/kernels", battery=Battery(),
            earth_margin=0.0, site_id="custom"):
    """Site report for a lander at (lat, lon) with panels and antenna `mast` m up, landing at `start`
    ('YYYY-MM-DDTHH', UTC) for a mission of `days` days."""
    lon = (lon + 180.0) % 360.0 - 180.0
    x, y = latlon_to_xy(lat, lon)
    xs, ys = np.array([x], float), np.array([y], float)
    coarse_dem = read_polar_dem(coarse)
    terrain = (multires(read_polar_dem(fine, fine_bounds(xs, ys, D_FINE)), coarse_dem, D_FINE)
               if fine else single(coarse_dem))
    H, D, ok = (a[0] for a in horizon_profiles_fast(terrain, xs, ys, mast, D_MAX, N_AZ, KAPPA))
    ground, slope = height_and_slope(terrain.levels[0], x, y)

    t = np.datetime64(start, "h")
    day = t.astype("datetime64[D]")
    offset, hours = int((t - day) / np.timedelta64(1, "h")), int(round(days * 24))
    load_kernels(kernels)
    times, sun_az, sun_el, earth_az, earth_el, sun_r, earth_r = make_sky(
        [site_id], np.array([lat]), np.array([lon]), np.array([ground]), str(day), offset + hours)
    w = slice(offset, offset + hours)
    track = {"time_utc": times[w], "sun_az": sun_az[0, w], "sun_el": sun_el[0, w], "earth_az": earth_az[0, w],
             "earth_el": earth_el[0, w], "sun_radius_deg": sun_r[w], "earth_radius_deg": earth_r[w]}
    site = {"id": site_id, "lat": round(lat, 5), "lon": round(lon, 4), "x_m": round(x, 1), "y_m": round(y, 1),
            "ground_m": round(ground, 1), "slope_deg": round(slope, 1), "terrain": [Path(f).name for f in (fine, coarse) if f]}
    return site_report(site, H, D, ok, track, mast, battery, earth_margin)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--mast", type=float, default=2.0, help="height of panels and antenna above the ground (m)")
    ap.add_argument("--start", required=True, help="landing time, UTC: YYYY-MM-DDTHH")
    ap.add_argument("--days", type=float, default=14, help="mission length")
    ap.add_argument("--coarse", required=True, help="PDS3 label of the 240 m map")
    ap.add_argument("--fine", help="PDS3 label of a 20 m map covering 40 km around the site")
    ap.add_argument("--kernels", default="data/kernels")
    ap.add_argument("--earth-margin", type=float, default=0.0, help="degrees Earth must clear the skyline by")
    ap.add_argument("--id", default="custom", help="site id in the report")
    ap.add_argument("--out", required=True, help="where to write the report (.json)")
    for name, default in vars(Battery()).items():
        ap.add_argument(f"--{name.replace('_', '-')}", type=float, default=default, help=f"battery {name}")
    a = ap.parse_args()

    battery = Battery(a.e_max, a.e_min, a.p_panel, a.p_load, a.dt)
    report = analyze(a.lat, a.lon, a.mast, a.start, a.days, a.coarse, a.fine, a.kernels, battery, a.earth_margin, a.id)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report))
    print("\n".join(report["verdict"] + report["why"]))
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
