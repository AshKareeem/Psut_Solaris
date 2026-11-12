"""Validate the engine against NASA's PGDA maps, pixel by pixel.

Runs the engine at the centre of every pixel in an n x n block of NASA's 60 m maps around a site, with 20 m terrain
near each pixel and the 240 m map beyond, and computes Sun and Earth visibility the way NASA's maps define it, with
the pipeline's own Step 2 sky (NASA SPICE, scripts/make_sky.py) and Step 3 formulas (scripts/events.py):
  Sun:   average visible fraction of the Sun's disc, every hour over 18.6 years (one lunar nutation cycle)
  Earth: share of those hours with any part of Earth's disc visible
(PGDA product 69: "averaged over hourly timesteps spanning 18.6 years"; Earth "visible if any part of its disc is
not obscured"; Mazarico et al. 2011). It compares them with NASA's values for several observer heights:
correlation, average difference (ours - NASA, in percentage points) and the share of pixels within 10 points.
NASA does not state its observer height, so the best match is an observed fit, not a fact about their setup.
Writes a scatter plot against the 1:1 line.

Usage:
  python scripts/validate_pgda.py data/ldem_75s_240m.lbl data/ldem_875s_20m.lbl data/AVGVISIB_85S_060M_201608.TIF data/AVGVISIB_85S_060M_201608_EARTH.TIF
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon import D_FINE, D_MAX, KAPPA, N_AZ  # noqa: E402
from horizon.dem import latlon_to_xy, read_polar_dem  # noqa: E402
from horizon.fast import horizon_profiles_fast  # noqa: E402
from horizon.reference import bilinear  # noqa: E402
from horizon.sites import RIM_SITE  # noqa: E402
from horizon.terrain import fine_bounds, multires  # noqa: E402
from scripts.compare_pgda import read_window  # noqa: E402
from scripts.events import earth_clearance, sun_clearance, sun_fraction  # noqa: E402
from scripts.make_sky import load_kernels, make_sky  # noqa: E402

NUTATION_DAYS = 6794                 # 18.6 years: the lunar nutation cycle NASA's averages span, hourly


def visibility(H, sky):
    """Average visible fraction of the Sun's disc and share of hours with Earth in view, per pixel: H [pixels, n_az]."""
    sun = sun_fraction(sun_clearance(H, sky["sun_az"], sky["sun_el"]), sky["sun_r"][None]).mean(axis=1)
    earth = (earth_clearance(H, sky["earth_az"], sky["earth_el"], sky["earth_r"][None], 0.0) > 0).mean(axis=1)
    return sun, earth


def agreement(ours, nasa):
    """Correlation, average difference (ours - NASA) in percentage points, and the share within 10 points."""
    diff = (ours - nasa) * 100
    return np.corrcoef(ours, nasa)[0, 1], diff.mean(), np.mean(np.abs(diff) <= 10)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("coarse", help="PDS3 label of the 240 m map")
    ap.add_argument("fine", help="PDS3 label of the 20 m map")
    ap.add_argument("sun", help="NASA PGDA Sun visibility GeoTIFF")
    ap.add_argument("earth", help="NASA PGDA Earth visibility GeoTIFF")
    ap.add_argument("--lat", type=float, default=RIM_SITE[0])
    ap.add_argument("--lon", type=float, default=RIM_SITE[1])
    ap.add_argument("--n", type=int, default=10, help="block of n x n NASA pixels around the site")
    ap.add_argument("--masts", type=float, nargs="+", default=[0.0, 2.0, 5.0, 10.0], help="observer heights (m)")
    ap.add_argument("--start", default="2008-01-01", help="first day of the 18.6-year hourly sky")
    ap.add_argument("--kernels", default="data/kernels", help="folder with the NASA SPICE files")
    ap.add_argument("--out", default="out/validate_pgda.png")
    args = ap.parse_args()

    sun, lat_c, lon_c, _ = read_window(args.sun, args.lat, args.lon, args.n)
    earth, lat_e, lon_e, _ = read_window(args.earth, args.lat, args.lon, args.n)
    if not (np.allclose(lat_c, lat_e) and np.allclose(lon_c, lon_e)):
        raise SystemExit("the Sun and Earth maps are on different grids")
    keep = ~(np.ma.getmaskarray(sun) | np.ma.getmaskarray(earth)).ravel()
    nasa = {"Sun": np.ma.getdata(sun).ravel()[keep], "Earth": np.ma.getdata(earth).ravel()[keep]}
    xs, ys = latlon_to_xy(lat_c.ravel()[keep], lon_c.ravel()[keep])
    coarse = read_polar_dem(args.coarse)
    terrain = multires(read_polar_dem(args.fine, fine_bounds(xs, ys, D_FINE)), coarse, D_FINE)
    ground = bilinear(terrain.levels[0].height, *terrain.levels[0].xy_to_rowcol(xs, ys)[::-1])
    load_kernels(args.kernels)
    _, *tracks = make_sky(np.arange(xs.size), lat_c.ravel()[keep], lon_c.ravel()[keep], ground, args.start,
                          NUTATION_DAYS * 24)
    sky = dict(zip(("sun_az", "sun_el", "earth_az", "earth_el", "sun_r", "earth_r"), tracks))
    print(f"{keep.sum()} NASA pixels ({args.n} x {args.n}) around {args.lat}, {args.lon} | engine: {Path(args.fine).name} "
          f"to {D_FINE / 1e3:.0f} km, then {Path(args.coarse).name} | {N_AZ} azimuths")

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for mast in args.masts:
        H = horizon_profiles_fast(terrain, xs, ys, mast, D_MAX, N_AZ, KAPPA)[0]
        ours = dict(zip(("Sun", "Earth"), visibility(H, sky)))
        line = f"mast {mast:>4} m"
        for ax, body in zip(axes, ("Sun", "Earth")):
            r, mean, within = agreement(ours[body], nasa[body])
            line += f" | {body}: correlation {r:.2f}, average difference {mean:+.1f} points, within 10 points {within:.0%}"
            ax.scatter(nasa[body] * 100, ours[body] * 100, s=18, label=f"mast {mast:g} m (r = {r:.2f})")
        print(line)
    for ax, body in zip(axes, ("Sun", "Earth")):
        ax.plot([0, 100], [0, 100], "k--", lw=1, label="1:1")
        ax.set(xlim=(0, 100), ylim=(0, 100), xlabel=f"NASA PGDA: {body} visible (% of time)",
               ylabel=f"our engine: {body} visible (% of time)", title=f"{body}, {keep.sum()} NASA pixels of 60 m")
        ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
