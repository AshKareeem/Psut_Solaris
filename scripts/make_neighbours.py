"""Points within 100 m of the top sites, for the landing-error check (team PDF, Step 4: worst score within 100 m).

For each top site in results.json: the site itself plus 8 directions at 50 m and 100 m (17 points). Writes a
sites.csv with an extra `parent` column (row of the parent site in the original sites.csv). Run the engine on it
(scripts/run_horizon.py), then scripts/score_sites.py --neighbours. Height and slope are the parent's (display
only: the engine takes the ground from the terrain). Within 6 deg of the pole the map scale is within 0.3% of
true, so 100 m on the map stays within 100 m on the ground.

Usage:
  python scripts/make_neighbours.py sites.csv out/results/results.json --out out/nb/sites.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import xy_to_latlon  # noqa: E402
from horizon.sites import COLUMNS  # noqa: E402

RINGS_M = (50.0, 100.0)
DIRECTIONS = 8


def offsets():
    """Map offsets (dx, dy) in metres: the centre, then each ring."""
    a = np.arange(DIRECTIONS) * 2 * np.pi / DIRECTIONS
    return [(0.0, 0.0)] + [(rr * np.cos(t), rr * np.sin(t)) for rr in RINGS_M for t in a]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sites", help="the sites.csv the results were made from")
    ap.add_argument("results", help="results.json from scripts/score_sites.py (uses meta.top_sites)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with open(a.sites, newline="") as f:
        rows = list(csv.DictReader(f))
    top = json.loads(Path(a.results).read_text())["meta"]["top_sites"]
    if not top:
        raise SystemExit("results.json has no top sites")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS + ("parent",))
        for p in top:
            row = rows[p]
            for k, (dx, dy) in enumerate(offsets()):
                x, y = float(row["x"]) + dx, float(row["y"]) + dy
                lat, lon = xy_to_latlon(x, y)
                w.writerow([f"{row['id']}_{k}", f"{x:.3f}", f"{y:.3f}", f"{lat:.8f}", f"{lon:.8f}",
                            row["height"], row["slope"], p])
    print(f"{len(top)} sites x {len(offsets())} points -> {a.out}")


if __name__ == "__main__":
    main()
