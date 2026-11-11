"""Terrain for the horizon engines: one map, or fine terrain near the sites and a coarse map beyond."""
from dataclasses import dataclass

import numpy as np

from horizon.reference import R


@dataclass
class Terrain:
    """Terrain levels (PolarDEMs), finest first. Level i serves the samples at distances >= starts[i]; starts[0] = 0."""
    levels: list
    starts: list

    def level_of(self, d):
        """Level index of each distance in d."""
        return np.searchsorted(self.starts, d, side="right") - 1

    def check_coverage(self, xs, ys, d):
        """Fail fast unless every site is on every level and each level but the last holds all of its samples."""
        level = self.level_of(d)
        for i, dem in enumerate(self.levels):
            served = d[level == i]
            reach = map_reach(xs, ys, served.max()) if i < len(self.levels) - 1 and served.size else 0.0
            rows, cols = dem.xy_to_rowcol(xs, ys)
            r = reach / dem.pixel
            ok = ((cols - r >= 0) & (rows - r >= 0)
                  & (cols + r < dem.height.shape[1] - 1) & (rows + r < dem.height.shape[0] - 1))
            if not ok.all():
                bad = np.flatnonzero(~ok)[:10].tolist()
                if np.all(reach == 0):
                    raise ValueError(f"sites {bad} are off the map")
                raise ValueError(f"sites {bad}: the {dem.pixel:g} m terrain does not reach "
                                 f"{served.max() / 1e3:.1f} km around them")


def map_reach(xs, ys, d):
    """Largest map distance (m) of any point within surface distance d of each site. The map stretches by
    sec^2(c/2) at angle c from the pole, and no point within d is farther from the pole than c_site + d/R."""
    c_far = 2 * np.arctan(np.hypot(xs, ys) / (2 * R)) + d / R
    return d / np.cos(c_far / 2) ** 2


def single(dem):
    return Terrain(levels=[dem], starts=[0.0])


def multires(fine, coarse, d_fine):
    """Fine terrain out to d_fine metres (along the surface) from each site, the coarse map beyond."""
    return Terrain(levels=[fine, coarse], starts=[0.0, d_fine])


def fine_bounds(xs, ys, d_fine):
    """Map bounds (x_min, x_max, y_min, y_max) that the fine terrain must cover for these sites."""
    reach = map_reach(xs, ys, d_fine)
    return np.min(xs - reach), np.max(xs + reach), np.min(ys - reach), np.max(ys + reach)
