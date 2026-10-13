"""Convergence study: the cheapest engine settings whose skyline stays within TOL of the finest settings.

Varies the range d_max, the step factor kappa and the number of azimuths n_az on real terrain, at the Shackleton
rim site plus random sites within 6 deg of the pole, for the tallest mast (it sees farthest, so range matters most).

Every (d_max, kappa) runs once on the finest azimuth grid. A coarser grid is every k-th of those rays, linearly
interpolated back onto the fine grid (the way Steps 3-4 interpolate H), so the error *between* rays is measured,
not just at rays both grids share. At 250 km the finest rays are 273 m apart, about one pixel of the 240 m map.

Usage:
  python scripts/convergence.py data/ldem_75s_240m.lbl
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import read_polar_dem  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.reference import step_schedule  # noqa: E402
from horizon.sites import RIM_SITE, random_sites  # noqa: E402

D_MAX = (100e3, 150e3, 200e3, 250e3)  # m
KAPPA = (0.002, 0.001, 0.0005)
N_AZ = (360, 720, 1440, 2880, 5760)   # the last one is the reference grid
TOL = 0.02                            # deg


def between_rays(H, every):
    """Profile from every `every`-th ray, linearly interpolated (periodic in azimuth) back onto all rays."""
    j = np.arange(H.shape[1])
    lo, f = j // every, (j % every) / every
    coarse = H[:, ::every]
    return coarse[:, lo] * (1 - f) + coarse[:, (lo + 1) % coarse.shape[1]] * f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("--sites", type=int, default=200, help="random sites within 6 deg of the pole, plus the rim site")
    ap.add_argument("--mast", type=float, default=10.0, help="observer height (m); the tallest mast sees farthest")
    args = ap.parse_args()

    dem = read_polar_dem(args.label)
    rim_row, rim_col = dem.latlon_to_rowcol(*RIM_SITE)
    rows, cols = random_sites(dem, args.sites, 6.0, np.random.default_rng(0))
    rows, cols = np.append(rim_row, rows), np.append(rim_col, cols)  # site 0 is the rim site
    fine = N_AZ[-1]

    def skyline(d_max, kappa):
        H, _, ok = horizon_profiles_fast(dem.height, dem.pixel, cols, rows, args.mast, d_max, fine, kappa)
        if not ok.all():
            raise SystemExit(f"{np.sum(~ok)} rays left the map at d_max {d_max / 1e3:.0f} km: "
                             f"the map must reach 6 deg + {D_MAX[-1] / 1e3:.0f} km from the pole")
        return H

    print(f"{Path(args.label).name} | {cols.size} sites (rim + {args.sites} random within 6 deg) | mast {args.mast} m "
          f"| reference: {fine} azimuths, d_max {D_MAX[-1] / 1e3:.0f} km, kappa {KAPPA[-1]}")
    ref = skyline(D_MAX[-1], KAPPA[-1])
    results = []
    for d_max in D_MAX:
        for kappa in KAPPA:
            H = ref if (d_max, kappa) == (D_MAX[-1], KAPPA[-1]) else skyline(d_max, kappa)
            steps = step_schedule(dem.pixel, d_max, kappa).size
            for n in N_AZ:
                err = np.abs(between_rays(H, fine // n) - ref)
                results.append((n * steps, n, d_max, kappa, steps, err.max(), np.quantile(err, 0.99), err[0].max()))

    results.sort()
    chosen = next(r for r in results if r[5] < TOL)
    print(f"\n{'n_az':>5} {'d_max':>7} {'kappa':>7} {'steps':>6} {'samples/site':>13} "
          f"{'max err':>9} {'99% err':>9} {'rim max':>9}")
    for r in results:
        cost, n, d_max, kappa, steps, e_max, e_99, e_rim = r
        mark = "  <- cheapest within tolerance" if r is chosen else ""
        print(f"{n:>5} {d_max / 1e3:>5.0f}km {kappa:>7} {steps:>6} {cost:>13,} "
              f"{e_max:>9.4f} {e_99:>9.4f} {e_rim:>9.4f}{mark}")
    cost, n, d_max, kappa, steps, e_max, e_99, e_rim = chosen
    print(f"\nchosen (max error < {TOL} deg over {cols.size} sites x {fine} directions): "
          f"n_az {n}, d_max {d_max / 1e3:.0f} km, kappa {kappa} | max error {e_max:.4f} deg, rim site {e_rim:.4f} deg")


if __name__ == "__main__":
    main()
