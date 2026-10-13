"""Time the fast engine on real LOLA terrain and extrapolate to the full site grid.

Sites are random points within 6 deg of the pole (the Artemis III zone), uniform in area.
"Samples" counts the nominal sites x azimuths x steps; early exit skips many of them, which is the point.

Usage:
  python scripts/benchmark.py data/ldem_75s_240m.lbl
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from numba import get_num_threads

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import read_polar_dem  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.reference import R, horizon_profile, step_schedule  # noqa: E402


def random_sites(dem, n, max_deg, rng):
    """Grid (cols, rows) of n random sites within max_deg of the pole, uniform in area."""
    r = np.radians(max_deg) * R * np.sqrt(rng.uniform(0, 1, n))
    a = rng.uniform(0, 2 * np.pi, n)
    return dem.center + r * np.cos(a) / dem.pixel, dem.center - r * np.sin(a) / dem.pixel


def timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("--sites", type=int, nargs="+", default=[1, 10, 100])
    ap.add_argument("--mast", type=float, default=2.0)
    ap.add_argument("--dmax", type=float, default=150_000.0)
    ap.add_argument("--n-az", type=int, default=1440)
    ap.add_argument("--kappa", type=float, default=0.002)
    args = ap.parse_args()

    dem = read_polar_dem(args.label)
    n_d = step_schedule(dem.pixel, args.dmax, args.kappa).size
    run = dict(mast=args.mast, d_max=args.dmax, n_az=args.n_az, kappa=args.kappa)
    rng = np.random.default_rng(0)
    print(f"{Path(args.label).name}: {dem.pixel:.0f} m pixels | {args.n_az} azimuths | d_max {args.dmax / 1e3:.0f} km "
          f"| kappa {args.kappa} | {n_d} steps per ray | {get_num_threads()} threads")

    cols, rows = random_sites(dem, 1, 6.0, rng)
    print(f"first call (includes compiling, or loading the compile cache): "
          f"{timed(lambda: horizon_profiles_fast(dem.height, dem.pixel, cols, rows, **run)):.2f} s")
    t_ref = timed(lambda: horizon_profile(dem.height, dem.pixel, cols[0], rows[0], **run))
    print(f"reference engine, 1 site: {t_ref:.2f} s")

    rate = 0.0
    for n in args.sites:
        cols, rows = random_sites(dem, n, 6.0, rng)
        t = timed(lambda: horizon_profiles_fast(dem.height, dem.pixel, cols, rows, **run))
        rate = n * args.n_az * n_d / t
        print(f"fast engine, {n:>5} sites: {t:7.2f} s | {t / n * 1e3:8.1f} ms per site | "
              f"{rate:.2e} samples/s | {t_ref * n / t:6.0f}x the reference")

    final_steps = step_schedule(20.0, 200_000.0, 0.002).size
    final = 10_000 * 4 * 1440 * final_steps
    print(f"full grid at this rate: 10,000 sites x 4 masts x 1440 azimuths x {final_steps} steps (20 m, 200 km) "
          f"= {final:.2e} samples -> about {final / rate / 60:.0f} min. Rough: the 20 m multi-resolution "
          f"terrain will change the rate.")


if __name__ == "__main__":
    main()
