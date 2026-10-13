"""Rough Sun and Earth visibility of one site from its saved skyline (plot_horizon.py --save).

These are estimates for checking the engine against NASA's PGDA maps, not the final answer:
exact Sun and Earth positions per hour come from SPICE (Step 2).

  - Sun: its height at the pole follows a yearly sine within +-SUN_MAX while it sweeps every
    direction each month, so the long-term average treats all directions equally.
  - Earth: sits near map direction EARTH_THETA (toward longitude 0) and bobs +-EARTH_MAX (libration).
  - Tilt: a site c degrees from the pole sees anything in direction theta c*cos(theta - theta_out)
    higher than the pole does, where theta_out points away from the pole.

Usage:
  python scripts/estimate_visibility.py out/rim.npz
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import latlon_to_xy  # noqa: E402

SUN_MAX = 1.54                       # deg: the Sun stays within this of level at the pole
SUN_RADIUS = 0.27                    # deg
EARTH_MAX = 6.7                      # deg: Earth bobs this far up and down (libration)
EARTH_RADIUS = 0.95                  # deg
EARTH_THETA, EARTH_HALF = 90.0, 8.0  # deg: Earth's direction on the map and its side-to-side swing


def tilt(lat, lon):
    """Angular distance from the pole c (deg) and the map direction pointing away from the pole (deg)."""
    x, y = latlon_to_xy(lat, lon)
    return 90.0 + lat, np.degrees(np.arctan2(y, x)) % 360


def sun_fraction(H, theta, c, theta_out):
    """Average fraction of the Sun's disc above the skyline over a year."""
    e = SUN_MAX * np.sin(2 * np.pi * np.arange(365) / 365)
    el = e[:, None] + c * np.cos(np.radians(theta - theta_out))[None, :]
    return np.clip((el - H[None, :] + SUN_RADIUS) / (2 * SUN_RADIUS), 0, 1).mean()


def earth_fraction(H, theta, c, theta_out):
    """Fraction of time any part of Earth's disc is above the skyline toward Earth."""
    H_earth = H[np.abs(theta - EARTH_THETA) <= EARTH_HALF].max()
    lift = c * np.cos(np.radians(EARTH_THETA - theta_out))
    return 0.5 - np.arcsin(np.clip((H_earth - EARTH_RADIUS - lift) / EARTH_MAX, -1, 1)) / np.pi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skyline", help=".npz written by plot_horizon.py --save")
    args = ap.parse_args()

    s = np.load(args.skyline)
    c, theta_out = tilt(float(s["lat"]), float(s["lon"]))
    print(f"site {float(s['lat']):.3f}, {float(s['lon']):.2f} | mast {float(s['mast'])} m | "
          f"{c:.3f} deg from the pole, away from it = theta {theta_out:.1f}")
    print(f"Sun: {sun_fraction(s['H'], s['theta'], c, theta_out):.1%} of the year "
          f"(no tilt: {sun_fraction(s['H'], s['theta'], 0.0, 0.0):.1%})")
    print(f"Earth: {earth_fraction(s['H'], s['theta'], c, theta_out):.1%} of the time "
          f"(no tilt: {earth_fraction(s['H'], s['theta'], 0.0, 0.0):.1%})")


if __name__ == "__main__":
    main()
