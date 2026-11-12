"""Named sites (named_sites.csv: id, name, kind, lat, lon, source) -> a sites.csv the pipeline reads.

For every site except kind out_of_coverage: map x, y (south polar stereographic), the ground height and the slope
over a 100 m baseline (NASA's Artemis gate: under 10 deg over 100 m) from the first --dem, finest first, that covers
the site. The map each site used is printed and written to the `terrain` column. Out-of-coverage sites (for example
Apollo 11, near the equator) are listed and skipped: our terrain is south-polar.

Usage:
  python scripts/named_to_sites.py named_sites.csv --dem data/ldem_80s_20m.lbl data/ldem_75s_240m.lbl --out out/named/sites.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import latlon_to_xy, map_half_width, read_polar_dem  # noqa: E402
from horizon.reference import bilinear  # noqa: E402
from horizon.sites import COLUMNS  # noqa: E402

BASELINE_M = 100.0
EXTRA = ("name", "kind", "source", "terrain")


def height_and_slope(dem, x, y):
    """Bilinear ground height at x, y and slope (deg) from central differences over BASELINE_M."""
    h = BASELINE_M / 2
    xs = np.array([x, x + h, x - h, x, x])
    ys = np.array([y, y, y, y + h, y - h])
    rows, cols = dem.xy_to_rowcol(xs, ys)
    z = bilinear(dem.height, cols, rows)
    if np.isnan(z).any():
        raise ValueError(f"terrain has no data around x {x:.0f}, y {y:.0f}")
    dzdx, dzdy = (z[1] - z[2]) / BASELINE_M, (z[3] - z[4]) / BASELINE_M
    return float(z[0]), float(np.degrees(np.arctan(np.hypot(dzdx, dzdy))))


def covering(labels, x, y):
    """First label whose map holds the whole 100 m baseline around x, y (with a 2 km margin)."""
    for label in labels:
        if max(abs(x), abs(y)) + BASELINE_M + 2000 < map_half_width(label):
            return label
    raise ValueError(f"no --dem covers x {x:.0f}, y {y:.0f}: download a map that reaches it")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("named", help="named_sites.csv")
    ap.add_argument("--dem", nargs="+", required=True, help="PDS3 labels, finest first")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with open(a.named, newline="") as f:
        named = list(csv.DictReader(f))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS + EXTRA)
        for s in named:
            if s["kind"] == "out_of_coverage":
                print(f"{s['id']:>18}: out of coverage (our terrain is south-polar), skipped")
                continue
            x, y = (float(v) for v in latlon_to_xy(float(s["lat"]), float(s["lon"])))
            label = covering(a.dem, x, y)
            dem = read_polar_dem(label, (x - 500, x + 500, y - 500, y + 500))
            height, slope = height_and_slope(dem, x, y)
            w.writerow([s["id"], f"{x:.3f}", f"{y:.3f}", s["lat"], s["lon"], f"{height:.2f}", f"{slope:.2f}",
                        s["name"], s["kind"], s["source"], Path(label).name])
            print(f"{s['id']:>18}: {Path(label).name}, height {height:.0f} m, slope {slope:.1f} deg over 100 m")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
