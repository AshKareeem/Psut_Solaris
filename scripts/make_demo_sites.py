"""Write a demo sites.csv in the Step 0 format: an n x n grid around a site (default: the Shackleton rim site).

Lets Steps 1, 3 and 4 run before Step 0's real candidate grid exists. Heights are the map's pixel values; slopes
come from two-pixel central differences, not the 100 m slope Step 0 will provide.

Usage:
  python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --out out/demo/sites.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import read_polar_dem  # noqa: E402
from horizon.sites import RIM_SITE, grid_around, write_sites  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("--out", default="out/demo/sites.csv")
    ap.add_argument("--lat", type=float, default=RIM_SITE[0])
    ap.add_argument("--lon", type=float, default=RIM_SITE[1])
    ap.add_argument("--n", type=int, default=20, help="grid is n x n sites")
    ap.add_argument("--step", type=int, default=2, help="pixels between neighbouring sites")
    args = ap.parse_args()

    dem = read_polar_dem(args.label)
    rows, cols = grid_around(dem, args.lat, args.lon, args.n, args.step)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_sites(args.out, dem, rows, cols)
    print(f"wrote {rows.size} sites ({args.n} x {args.n}, {args.step * dem.pixel:.0f} m apart, "
          f"site {args.n // 2 * (args.n + 1)} at {args.lat}, {args.lon}) to {args.out}")


if __name__ == "__main__":
    main()
