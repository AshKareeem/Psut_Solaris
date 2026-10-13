"""Terrain for the horizon engines: one map, or fine terrain near the sites and a coarse map beyond."""
from dataclasses import dataclass

import numpy as np


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
            reach = served.max() if i < len(self.levels) - 1 and served.size else 0.0
            rows, cols = dem.xy_to_rowcol(xs, ys)
            r = reach / dem.pixel
            ok = ((cols - r >= 0) & (rows - r >= 0)
                  & (cols + r < dem.height.shape[1] - 1) & (rows + r < dem.height.shape[0] - 1))
            if not ok.all():
                bad = np.flatnonzero(~ok)[:10].tolist()
                if reach == 0:
                    raise ValueError(f"sites {bad} are off the map")
                raise ValueError(f"sites {bad}: the {dem.pixel:g} m terrain does not reach {reach / 1e3:.1f} km around them")


def single(dem):
    return Terrain(levels=[dem], starts=[0.0])


def multires(fine, coarse, d_fine):
    """Fine terrain out to d_fine metres from each site, the coarse map beyond."""
    return Terrain(levels=[fine, coarse], starts=[0.0, d_fine])


def fine_bounds(xs, ys, d_fine):
    """Map bounds (x_min, x_max, y_min, y_max) that the fine terrain must cover for these sites."""
    return np.min(xs) - d_fine, np.max(xs) + d_fine, np.min(ys) - d_fine, np.max(ys) + d_fine
