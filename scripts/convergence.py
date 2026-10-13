"""Convergence study: the cheapest engine settings whose skyline stays within TOL of the finest settings.

One map: varies the range d_max, the step factor kappa and the number of azimuths n_az, at the Shackleton rim site
plus random sites within --within deg of the pole, for the tallest mast (it sees farthest, so range matters most).
With --fine: the range stays at the longest D_MAX and the first knob becomes d_fine, how far the fine terrain must reach.

Every combination runs once on the finest azimuth grid. A coarser grid is every k-th of those rays, linearly
interpolated back onto the fine grid (the way Steps 3-4 interpolate H), so the error *between* rays is measured,
not just at rays both grids share. The reference is twice as fine as any candidate, so every candidate is measured.

Rule: every site's skyline within TOL in 99% of its directions. Missing terrain (too short a range, too small a fine
area) shifts whole sectors of a site and fails it; isolated directions at sharp kinks near the site converge slowly
but do not move what planners see. The study prints the worst single direction too, and checks the chosen settings
against the reference in Sun and Earth visibility per site.

Usage:
  python scripts/convergence.py data/ldem_75s_240m.lbl
  python scripts/convergence.py data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --within 0.45 --sites 200
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import latlon_to_xy, read_polar_dem, xy_to_latlon  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.reference import step_schedule  # noqa: E402
from horizon.sites import RIM_SITE, random_sites  # noqa: E402
from horizon.terrain import fine_bounds, multires, single  # noqa: E402
from scripts.estimate_visibility import earth_fraction, sun_fraction, tilt  # noqa: E402

D_MAX = (100e3, 150e3, 200e3, 250e3)        # m
D_FINE = (5e3, 10e3, 20e3, 40e3, 60e3)      # m, with --fine
KAPPA = (0.002, 0.001, 0.0005, 0.00025)
N_AZ = (360, 720, 1440, 2880, 5760, 11520)  # the last one is the reference grid
TOL = 0.02                                  # deg, for 99% of each site's directions


def between_rays(H, every):
    """Profile from every `every`-th ray, linearly interpolated (periodic in azimuth) back onto all rays."""
    j = np.arange(H.shape[1])
    lo, f = j // every, (j % every) / every
    coarse = H[:, ::every]
    return coarse[:, lo] * (1 - f) + coarse[:, (lo + 1) % coarse.shape[1]] * f


def visibility(H, xs, ys):
    """Sun and Earth visibility of every site (scripts/estimate_visibility.py)."""
    theta = np.arange(H.shape[1]) * 360 / H.shape[1]
    tilts = [tilt(lat, lon) for lat, lon in zip(*xy_to_latlon(xs, ys))]
    return (np.array([sun_fraction(h, theta, *t) for h, t in zip(H, tilts)]),
            np.array([earth_fraction(h, theta, *t) for h, t in zip(H, tilts)]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("--fine", help="PDS3 label of a finer map: study how far it must reach (d_fine)")
    ap.add_argument("--within", type=float, default=6.0, help="random sites within this many deg of the pole")
    ap.add_argument("--sites", type=int, default=500, help="random sites, plus the rim site")
    ap.add_argument("--mast", type=float, default=10.0, help="observer height (m); the tallest mast sees farthest")
    args = ap.parse_args()

    coarse = read_polar_dem(args.label)
    xs, ys = random_sites(args.sites, args.within, np.random.default_rng(0))
    rim_x, rim_y = latlon_to_xy(*RIM_SITE)
    xs, ys = np.append(rim_x, xs), np.append(rim_y, ys)  # site 0 is the rim site
    if args.fine:
        fine = read_polar_dem(args.fine, fine_bounds(xs, ys, D_FINE[-1]))
        knob, setups = "d_fine", {d: (multires(fine, coarse, d), D_MAX[-1]) for d in D_FINE}
    else:
        knob, setups = "d_max", {d: (single(coarse), d) for d in D_MAX}
    finest = N_AZ[-1]

    def skyline(terrain, d_max, kappa):
        H, _, ok = horizon_profiles_fast(terrain, xs, ys, args.mast, d_max, finest, kappa)
        if not ok.all():
            raise SystemExit(f"{np.sum(~ok)} rays left the map at d_max {d_max / 1e3:.0f} km: "
                             f"the map must reach {args.within} deg + {d_max / 1e3:.0f} km from the pole")
        return H

    last = list(setups)[-1]
    print(f"{Path(args.label).name}{' + ' + Path(args.fine).name if args.fine else ''} | {xs.size} sites "
          f"(rim + {args.sites} random within {args.within} deg) | mast {args.mast} m | reference: {finest} azimuths, "
          f"{knob} {last / 1e3:.0f} km, kappa {KAPPA[-1]}")
    ref = skyline(*setups[last], KAPPA[-1])
    results = []
    for value, (terrain, d_max) in setups.items():
        for kappa in KAPPA:
            H = ref if (value, kappa) == (last, KAPPA[-1]) else skyline(terrain, d_max, kappa)
            steps = step_schedule(terrain.levels[0].pixel, d_max, kappa).size
            for n in N_AZ:
                err = np.abs(between_rays(H, finest // n) - ref)
                site_99 = np.quantile(err, 0.99, axis=1).max()  # the worst site's 99th percentile
                results.append((n * steps, n, value, kappa, steps, site_99, err.max(), err[0].max()))

    results.sort()
    chosen = next(r for r in results if r[5] < TOL)
    print(f"\n{'n_az':>5} {knob:>7} {'kappa':>8} {'steps':>6} {'samples/site':>13} "
          f"{'site 99%':>9} {'max err':>9} {'rim max':>9}")
    for r in results:
        cost, n, value, kappa, steps, site_99, e_max, e_rim = r
        mark = "  <- cheapest within tolerance" if r is chosen else ""
        print(f"{n:>5} {value / 1e3:>5.0f}km {kappa:>8} {steps:>6} {cost:>13,} "
              f"{site_99:>9.4f} {e_max:>9.4f} {e_rim:>9.4f}{mark}")
    cost, n, value, kappa, steps, site_99, e_max, e_rim = chosen
    sun0, earth0 = visibility(ref, xs, ys)
    sun, earth = visibility(skyline(*setups[value], kappa)[:, ::finest // n], xs, ys)
    print(f"\nchosen (every site within {TOL} deg in 99% of its directions; {xs.size} sites): n_az {n}, "
          f"{knob} {value / 1e3:.0f} km, kappa {kappa} | worst single direction {e_max:.4f} deg, rim site {e_rim:.4f} deg\n"
          f"visibility change vs the reference, worst site: Sun {np.abs(sun - sun0).max():.2%}, "
          f"Earth {np.abs(earth - earth0).max():.2%}")


if __name__ == "__main__":
    main()
