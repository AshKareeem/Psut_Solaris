"""Plot the horizon (skyline) of one site.

Real LOLA terrain:
  python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-floor
  python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-rim --mast 2 --save out/rim.npz
  python scripts/plot_horizon.py data/ldem_75s_240m.lbl --lat -89.5 --lon 200
Synthetic terrain (no download needed):
  python scripts/plot_horizon.py --synthetic --site shackleton-floor
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import PolarDEM, read_polar_dem  # noqa: E402
from horizon.reference import horizon_profile  # noqa: E402
from horizon.synthetic import bowl_crater, cone, distance_grid  # noqa: E402
from scripts.estimate_visibility import EARTH_HALF, EARTH_MAX, EARTH_THETA, SUN_MAX  # noqa: E402

SHACKLETON = (-89.67, 129.78)  # crater centre (deg); about 21 km wide and 4.2 km deep
SHACKLETON_RADIUS = 10_500.0   # m


def synthetic_dem():
    """A Shackleton-like crater plus two mountains on a 100 m grid, 160 km wide, pole in the middle."""
    dem = PolarDEM(height=np.zeros((1601, 1601), np.float32), pixel=100.0, center=800.0)
    row, col = dem.latlon_to_rowcol(*SHACKLETON)
    z = bowl_crater(distance_grid(1601, 100.0, row, col), SHACKLETON_RADIUS, depth=4200.0, rim=300.0)
    z += cone(distance_grid(1601, 100.0, 800 - 300, 800 + 250), peak=2500.0, base_radius=8000.0)
    z += cone(distance_grid(1601, 100.0, 800 + 350, 800 - 400), peak=1800.0, base_radius=6000.0)
    dem.height = z.astype(np.float32)
    return dem


def pick_site(dem, args):
    if args.site == "shackleton-floor":
        return dem.latlon_to_rowcol(*SHACKLETON)
    if args.site == "shackleton-rim":  # highest point on the rim ring
        row, col = dem.latlon_to_rowcol(*SHACKLETON)
        r = distance_grid(dem.height.shape[0], dem.pixel, row, col)
        ring = (r > 0.85 * SHACKLETON_RADIUS) & (r < 1.25 * SHACKLETON_RADIUS)
        k = np.nanargmax(np.where(ring, dem.height, -np.inf))
        return np.unravel_index(k, dem.height.shape)
    if args.lat is None or args.lon is None:
        raise SystemExit("give --site or both --lat and --lon")
    return dem.latlon_to_rowcol(args.lat, args.lon)


def summarize(H, theta, ok, lat, lon, ground, mast):
    earth = (theta >= EARTH_THETA - EARTH_HALF) & (theta <= EARTH_THETA + EARTH_HALF)
    print(f"site {lat:.3f}, {lon:.2f} | ground {ground:.0f} m | mast {mast} m")
    print(f"horizon: min {H.min():.2f}, mean {H.mean():.2f}, max {H.max():.2f} deg")
    print(f"directions where the Sun can clear the skyline at its highest (H < {SUN_MAX}): {np.mean(H < SUN_MAX):.0%}")
    print(f"directions where it always clears (H < -{SUN_MAX}): {np.mean(H < -SUN_MAX):.0%}")
    print(f"Earth direction: skyline at {H[earth].max():.2f} deg (Earth rises at most {EARTH_MAX} deg)")
    if not ok.all():
        print(f"WARNING: {np.sum(~ok)} rays left the map before full range; extend the map or lower --dmax")


def plot(dem, row, col, H, D, theta, title, out):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.6), gridspec_kw={"width_ratios": [1, 1.7]})

    half = int(40_000 / dem.pixel)  # 40 km around the site
    r0, c0 = int(round(row)), int(round(col))
    crop = dem.height[max(r0 - half, 0):r0 + half, max(c0 - half, 0):c0 + half]
    ext = [-(c0 - max(c0 - half, 0)) * dem.pixel / 1e3, (min(c0 + half, dem.height.shape[1]) - c0) * dem.pixel / 1e3,
           -(min(r0 + half, dem.height.shape[0]) - r0) * dem.pixel / 1e3, (r0 - max(r0 - half, 0)) * dem.pixel / 1e3]
    im = ax1.imshow(crop, cmap="gray", extent=ext)
    fig.colorbar(im, ax=ax1, label="height (m)", shrink=0.8)
    bx, by = D * np.cos(np.radians(theta)) / 1e3, D * np.sin(np.radians(theta)) / 1e3
    near = (np.abs(bx) < 40) & (np.abs(by) < 40)
    ax1.scatter(bx[near], by[near], s=2, c="tab:orange", label="terrain forming the skyline")
    ax1.plot(0, 0, "r+", ms=14, mew=2, label="site")
    ax1.set(xlabel="km (map x)", ylabel="km (map y, toward longitude 0)", title="Terrain around the site")
    ax1.legend(loc="lower left", fontsize=8)

    low = min(-8.0, H.min() - 1)
    ax2.fill_between(theta, low, H, color="0.55", label="horizon profile H(θ)")
    ax2.axhspan(-SUN_MAX, SUN_MAX, color="gold", alpha=0.35, label=f"Sun's height range (±{SUN_MAX}°)")
    ax2.add_patch(plt.Rectangle((EARTH_THETA - EARTH_HALF, -EARTH_MAX), 2 * EARTH_HALF, 2 * EARTH_MAX,
                                color="tab:blue", alpha=0.3, label="Earth's zone (approx.)"))
    ax2.set(xlim=(0, 360), ylim=(low, max(10.0, H.max() + 2)), xticks=range(0, 361, 45),
            xlabel="direction θ (deg from map +x, counterclockwise)", ylabel="elevation (deg)", title=title)
    ax2.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    print(f"saved {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("label", nargs="?", help="PDS3 label (.LBL) of a south-polar LOLA DEM")
    ap.add_argument("--synthetic", action="store_true", help="use built-in synthetic terrain")
    ap.add_argument("--site", choices=["shackleton-floor", "shackleton-rim"])
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--mast", type=float, default=2.0, help="observer height above ground (m)")
    ap.add_argument("--dmax", type=float, default=150_000.0, help="look-out range (m)")
    ap.add_argument("--n-az", type=int, default=1440)
    ap.add_argument("--kappa", type=float, default=0.002)
    ap.add_argument("--out", default="out/horizon.png")
    ap.add_argument("--save", help="also save the skyline (H, D, theta, ok, lat, lon, mast) to this .npz")
    args = ap.parse_args()

    if args.synthetic == bool(args.label):
        raise SystemExit("give either a .LBL file or --synthetic")
    dem = synthetic_dem() if args.synthetic else read_polar_dem(args.label)
    row, col = pick_site(dem, args)
    lat, lon = dem.rowcol_to_latlon(row, col)
    ground = float(dem.height[int(round(row)), int(round(col))])

    H, D, ok = horizon_profile(dem.height, dem.pixel, col, row, args.mast, args.dmax, args.n_az, args.kappa)
    theta = np.arange(args.n_az) * 360.0 / args.n_az
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        np.savez(args.save, H=H, D=D, theta=theta, ok=ok, lat=lat, lon=lon, mast=args.mast)
        print(f"saved {args.save}")
    summarize(H, theta, ok, float(lat), float(lon), ground, args.mast)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    name = args.site or f"{lat:.2f}, {lon:.2f}"
    plot(dem, row, col, H, D, theta, f"Skyline: {name} ({'synthetic' if args.synthetic else 'LOLA'})", args.out)


if __name__ == "__main__":
    main()
