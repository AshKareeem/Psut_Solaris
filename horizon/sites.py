"""Candidate sites: the sites.csv contract between Step 0 and Steps 1 and 4, plus site sets for studies and demos.

sites.csv columns: id, x, y (map metres, south polar stereographic), lat, lon (deg), height (m), slope (deg).
"""
import csv

import numpy as np

from horizon.dem import latlon_to_xy, xy_to_latlon
from horizon.reference import R

COLUMNS = ("id", "x", "y", "lat", "lon", "height", "slope")
RIM_SITE = (-89.779, -155.73)  # Shackleton rim: highest rim point on the 240 m map (plot_horizon.py --site shackleton-rim)


def read_sites(path):
    """ids, x, y of every site. Fails fast on missing columns or lat/lon that disagree with x/y by over 1 m."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = sorted(set(COLUMNS) - set(reader.fieldnames or ()))
        if missing:
            raise ValueError(f"{path} is missing columns {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path} has no sites")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path} has duplicate site ids")
    x, y, lat, lon = (np.array([float(r[k]) for r in rows]) for k in ("x", "y", "lat", "lon"))
    px, py = latlon_to_xy(lat, lon)
    off = np.hypot(px - x, py - y)
    if off.max() > 1:
        raise ValueError(f"{path}: x, y disagree with lat, lon by up to {off.max():.0f} m (sites "
                         f"{np.flatnonzero(off > 1)[:10].tolist()}...); expected south polar stereographic, R = 1737.4 km")
    return ids, x, y


def write_sites(path, dem, rows, cols):
    """Write sites at integer grid positions (rows, cols) of dem, with their height and slope."""
    rows, cols = np.asarray(rows), np.asarray(cols)
    x, y = (cols - dem.center) * dem.pixel, (dem.center - rows) * dem.pixel
    lat, lon = xy_to_latlon(x, y)
    height, slope = dem.height[rows, cols], slope_deg(dem, rows, cols)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for i in range(rows.size):
            w.writerow([i, f"{x[i]:.3f}", f"{y[i]:.3f}", f"{lat[i]:.8f}", f"{lon[i]:.8f}",
                        f"{height[i]:.2f}", f"{slope[i]:.2f}"])


def slope_deg(dem, rows, cols):
    """Slope at grid positions from central differences over two pixels. Demo only: Step 0 owns the 100 m slope."""
    dzdx = (dem.height[rows, cols + 1] - dem.height[rows, cols - 1]) / (2 * dem.pixel)
    dzdy = (dem.height[rows - 1, cols] - dem.height[rows + 1, cols]) / (2 * dem.pixel)
    return np.degrees(np.arctan(np.hypot(dzdx, dzdy)))


def grid_around(dem, lat, lon, n, step):
    """n x n grid of integer (rows, cols), step pixels apart, with the pixel nearest (lat, lon) on it."""
    row, col = (int(round(float(v))) for v in dem.latlon_to_rowcol(lat, lon))
    offsets = (np.arange(n) - n // 2) * step
    rr, cc = np.meshgrid(row + offsets, col + offsets, indexing="ij")
    if min(rr.min(), cc.min()) < 1 or rr.max() > dem.height.shape[0] - 2 or cc.max() > dem.height.shape[1] - 2:
        raise ValueError(f"a {n} x {n} grid {step} pixels apart around {lat}, {lon} runs off the map")
    return rr.ravel(), cc.ravel()


def random_sites(dem, n, max_deg, rng):
    """Grid (rows, cols) of n random sites within max_deg of the pole, uniform in area."""
    r = np.radians(max_deg) * R * np.sqrt(rng.uniform(0, 1, n))
    a = rng.uniform(0, 2 * np.pi, n)
    return dem.center - r * np.sin(a) / dem.pixel, dem.center + r * np.cos(a) / dem.pixel
