"""Step 1 batch run: the skyline of every site at every mast height, in the files Steps 3-4 read (team PDF, Table 1).

Writes into --out:
  horizon.npy        float32 [sites, masts, n_az]  horizon elevation H, degrees
  blocker.npy        float32 [sites, masts, n_az]  distance to the terrain that forms the skyline, metres
  complete.npy       bool    [sites, masts, n_az]  False if the ray left the map before d_max
  horizon_meta.json  settings and conventions: read n_az and masts from here, never assume them
Site i is row i of the sites file. Azimuth j is theta = j * 360 / n_az degrees from map +x, counterclockwise.

Usage:
  python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --out out/demo/sites.csv
  python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --out out/demo
  python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --fine data/ldem_875s_20m.lbl --out out/demo
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon import D_FINE, D_MAX, KAPPA, N_AZ  # noqa: E402
from horizon.dem import read_polar_dem  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.reference import R  # noqa: E402
from horizon.sites import read_sites  # noqa: E402
from horizon.terrain import fine_bounds, multires, single  # noqa: E402

MASTS = (0.0, 2.0, 5.0, 10.0)  # m: the Sun check uses panel height, the Earth check antenna height


def skylines(terrain, xs, ys, masts, d_max, n_az, kappa):
    """H and D (float32) and complete, each [sites, masts, n_az]."""
    runs = [horizon_profiles_fast(terrain, xs, ys, m, d_max, n_az, kappa) for m in masts]
    H, D, ok = (np.stack(a, axis=1) for a in zip(*runs))
    return H.astype(np.float32), D.astype(np.float32), ok


def write_outputs(out_dir, H, D, ok, meta):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "horizon.npy", H)
    np.save(out / "blocker.npy", D)
    np.save(out / "complete.npy", ok)
    (out / "horizon_meta.json").write_text(json.dumps(meta, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("sites", help="sites.csv (id, x, y, lat, lon, height, slope)")
    ap.add_argument("--fine", help="PDS3 label of a finer map for the terrain near the sites")
    ap.add_argument("--dfine", type=float, default=D_FINE, help="how far from each site the fine map serves (m)")
    ap.add_argument("--out", default="out/horizon")
    ap.add_argument("--masts", type=float, nargs="+", default=list(MASTS), help="observer heights (m)")
    ap.add_argument("--dmax", type=float, default=D_MAX, help="look-out range (m)")
    ap.add_argument("--n-az", type=int, default=N_AZ)
    ap.add_argument("--kappa", type=float, default=KAPPA)
    args = ap.parse_args()

    coarse = read_polar_dem(args.label)
    ids, x, y = read_sites(args.sites)
    terrain = (multires(read_polar_dem(args.fine, fine_bounds(x, y, args.dfine)), coarse, args.dfine)
               if args.fine else single(coarse))
    t0 = time.perf_counter()
    H, D, ok = skylines(terrain, x, y, args.masts, args.dmax, args.n_az, args.kappa)
    seconds = time.perf_counter() - t0
    meta = {
        "n_sites": len(ids),
        "n_az": args.n_az,
        "azimuth": "theta_j = j * 360 / n_az deg, from map +x (toward 90E), counterclockwise; 90 deg = toward lon 0",
        "masts_m": args.masts,
        "d_max_m": args.dmax,
        "kappa": args.kappa,
        "R_m": R,
        "dem_files": [Path(f).name for f in (args.fine, args.label) if f],  # finest first
        "dem_starts_m": terrain.starts,  # each file serves samples from this distance on
        "sites_file": Path(args.sites).name,
        "arrays": {"horizon.npy": "float32 [sites, masts, n_az], horizon elevation, deg",
                   "blocker.npy": "float32 [sites, masts, n_az], distance to the terrain forming the skyline, m",
                   "complete.npy": "bool [sites, masts, n_az], False if the ray left the map before d_max_m"},
    }
    write_outputs(args.out, H, D, ok, meta)
    print(f"{len(ids)} sites x {len(args.masts)} masts x {args.n_az} azimuths in {seconds:.1f} s -> {args.out}")
    if not ok.all():
        print(f"WARNING: {np.sum(~ok.all(axis=(1, 2)))} sites have rays that left the map (see complete.npy)")


if __name__ == "__main__":
    main()
