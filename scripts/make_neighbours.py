"""Points within 100 m of the ranked sites, for the landing-error check (NASA: land within 100 m of the target).

For each site in any list of meta.top_sites_by_mast, in any of the results.json files given (one per lander preset,
scripts/run_profiles.py), so one engine run serves them all: the site itself plus 8 directions at 50 m and
100 m (17 points). Writes a sites.csv with an extra `parent` column (row of the parent site in the original sites.csv). Run the engine on it
(scripts/run_horizon.py), then scripts/score_sites.py --neighbours. Each point's height and slope are its own,
over 100 m on --slope-dem (the finest map: scripts/named_to_sites.py height_and_slope), because the landing-error
check needs ground under 10 deg at every point a lander could come down on (council R3, option A). Within 6 deg of
the pole the map scale is within 0.3% of true, so 100 m on the map stays within 100 m on the ground.

Usage:
  python scripts/make_neighbours.py sites.csv out/results/results.json --slope-dem data/ldem_80s_20m.lbl --out out/nb/sites.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import read_polar_dem, xy_to_latlon  # noqa: E402
from horizon.sites import COLUMNS  # noqa: E402
from scripts.named_to_sites import BASELINE_M, height_and_slope  # noqa: E402

RINGS_M = (50.0, 100.0)
DIRECTIONS = 8


def offsets():
    """Map offsets (dx, dy) in metres: the centre, then each ring."""
    a = np.arange(DIRECTIONS) * 2 * np.pi / DIRECTIONS
    return [(0.0, 0.0)] + [(rr * np.cos(t), rr * np.sin(t)) for rr in RINGS_M for t in a]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sites", help="the sites.csv the results were made from")
    ap.add_argument("results", nargs="+", help="results.json files from scripts/score_sites.py (uses "
                                               "meta.top_sites_by_mast of each)")
    ap.add_argument("--slope-dem", required=True, help="finest PDS3 label covering the points, for the 100 m slope")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with open(a.sites, newline="") as f:
        rows = list(csv.DictReader(f))
    row_of = {row["id"]: i for i, row in enumerate(rows)}
    lists = [json.loads(Path(p).read_text())["meta"]["top_sites_by_mast"] for p in a.results]
    top = sorted({row_of[site_id] for by_mast in lists for ids in by_mast.values() for site_id in ids})
    if not top:
        raise SystemExit("results.json ranks no sites")
    points = [(p, k, float(rows[p]["x"]) + dx, float(rows[p]["y"]) + dy)
              for p in top for k, (dx, dy) in enumerate(offsets())]
    xs, ys = [q[2] for q in points], [q[3] for q in points]
    pad = BASELINE_M + 100.0
    dem = read_polar_dem(a.slope_dem, bounds=(min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS + ("parent",))
        for p, k, x, y in points:
            lat, lon = xy_to_latlon(x, y)
            height, slope = height_and_slope(dem, x, y)
            w.writerow([f"{rows[p]['id']}_{k}", f"{x:.3f}", f"{y:.3f}", f"{lat:.8f}", f"{lon:.8f}",
                        f"{height:.2f}", f"{slope:.2f}", p])
    print(f"{len(top)} sites x {len(offsets())} points -> {a.out}")


if __name__ == "__main__":
    main()
