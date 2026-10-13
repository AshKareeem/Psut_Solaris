"""Fast horizon engine: many sites at once, compiled with Numba, same answers as horizon.reference.

Same geometry and arithmetic as the reference, plus the speed tricks of study guide section 3.4:
  1. d, cos(phi), sin(phi), cos(theta), sin(theta) are computed once, outside the loops
  2. compare tangents, not angles: one atan per ray, done at the end
  3. exact early exit: bound(k) caps the tangent of anything at distance >= d[k] and shrinks with k,
     so once the best tangent so far reaches it, nothing farther can win
  4. sites run in parallel over all CPU cores (prange)
"""
import math

import numpy as np
from numba import njit, prange

from horizon.reference import R, bilinear, step_schedule


def horizon_profiles_fast(dem, pixel, cols, rows, mast, d_max, n_az=1440, kappa=0.001):
    """Horizon for many sites at once.

    dem         float32 [n, n] heights in metres
    cols, rows  1-D arrays of site positions (fractional grid indices), same order as the reference
    returns     H [sites, n_az] degrees, D [sites, n_az] metres, complete [sites, n_az] bool
    """
    cols = np.asarray(cols, dtype=np.float64)
    rows = np.asarray(rows, dtype=np.float64)
    z0 = bilinear(dem, cols, rows)
    if np.isnan(z0).any():
        bad = np.flatnonzero(np.isnan(z0)).tolist()
        raise ValueError(f"sites {bad} are off the map or on a no-data pixel")

    theta = np.arange(n_az) * (2 * np.pi / n_az)        # from map +x, counterclockwise
    d = step_schedule(pixel, d_max, kappa)
    phi = d / R
    r_obs = R + z0 + mast
    # tallest terrain anywhere, +1 m so rounding can never put a sample above the bound
    top = R + np.maximum(np.nanmax(dem), z0 + mast) + 1.0
    tan_best, k_best, complete = _march(dem, float(pixel), cols, rows, r_obs, top,
                                        np.cos(theta), np.sin(theta), d, np.cos(phi), np.sin(phi))
    return np.degrees(np.arctan(tan_best)), d[k_best], complete


@njit(parallel=True, cache=True)
def _march(dem, pixel, cols, rows, r_obs, top, cos_t, sin_t, d, cos_p, sin_p):
    """Best tangent, its step index and the completeness flag for every site and azimuth."""
    n_sites, n_az, n_d = cols.size, cos_t.size, d.size
    nr, nc = dem.shape
    tan_best = np.empty((n_sites, n_az))
    k_best = np.empty((n_sites, n_az), np.int64)
    complete = np.empty((n_sites, n_az), np.bool_)
    for s in prange(n_sites):
        for j in range(n_az):
            best, best_k = -np.inf, 0
            for k in range(n_d):
                if best >= (top[s] * cos_p[k] - r_obs[s]) / (top[s] * sin_p[k]):
                    break                               # nothing at this distance or farther can beat best
                col = cols[s] + cos_t[j] * d[k] / pixel
                row = rows[s] - sin_t[j] * d[k] / pixel  # map +y = smaller row index
                if not _inside(col, row, nr, nc):
                    break                               # left the map; a straight ray never comes back
                z = _interp(dem, col, row)
                if math.isnan(z):
                    continue                            # no-data hole: skip the sample
                r_pt = R + z
                t = (r_pt * cos_p[k] - r_obs[s]) / (r_pt * sin_p[k])
                if t > best:                            # strict: ties keep the nearest, like np.argmax
                    best, best_k = t, k
            tan_best[s, j], k_best[s, j] = best, best_k
            col = cols[s] + cos_t[j] * d[n_d - 1] / pixel
            row = rows[s] - sin_t[j] * d[n_d - 1] / pixel
            # same meaning as the reference: the last sample has valid terrain, whatever the early exit did
            complete[s, j] = _inside(col, row, nr, nc) and not math.isnan(_interp(dem, col, row))
    return tan_best, k_best, complete


@njit(cache=True)
def _inside(col, row, nr, nc):
    """Same in-bounds rule as reference.bilinear."""
    c0, r0 = math.floor(col), math.floor(row)
    return c0 >= 0 and r0 >= 0 and c0 < nc - 1 and r0 < nr - 1


@njit(cache=True)
def _interp(dem, col, row):
    """Bilinear height at a point inside the map, in the same operation order as reference.bilinear."""
    c0, r0 = math.floor(col), math.floor(row)
    fc, fr = col - c0, row - r0
    return (dem[r0, c0] * (1 - fc) * (1 - fr) + dem[r0, c0 + 1] * fc * (1 - fr)
            + dem[r0 + 1, c0] * (1 - fc) * fr + dem[r0 + 1, c0 + 1] * fc * fr)
