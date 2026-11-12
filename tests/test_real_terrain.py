"""Real-data regression tests (CLAUDE.md section 9): results the team quotes, pinned so a refactor can't change them
silently. Skipped when the LOLA maps are not in data/."""
from pathlib import Path

import numpy as np
import pytest

from horizon import D_FINE, D_MAX, KAPPA, N_AZ
from horizon.dem import latlon_to_xy, read_polar_dem
from horizon.fast import horizon_profiles_fast
from horizon.reference import bilinear
from horizon.sites import RIM_SITE
from horizon.terrain import fine_bounds, multires, single
from scripts.estimate_visibility import visibility
from scripts.plot_horizon import SHACKLETON

DATA = Path(__file__).resolve().parents[1] / "data"
LOLA, LOLA_20M = DATA / "ldem_75s_240m.lbl", DATA / "ldem_875s_20m.lbl"
needs_240m = pytest.mark.skipif(not LOLA.exists(), reason="data/ldem_75s_240m.lbl missing")
needs_20m = pytest.mark.skipif(not (LOLA.exists() and LOLA_20M.exists()), reason="LOLA 20 m or 240 m map missing")


def skyline(terrain, x, y, mast):
    return horizon_profiles_fast(terrain, np.atleast_1d(x), np.atleast_1d(y), mast, D_MAX, N_AZ, KAPPA)[0]


def near_field(xs, ys):
    return multires(read_polar_dem(LOLA_20M, fine_bounds(xs, ys, D_FINE)), read_polar_dem(LOLA), D_FINE)


@needs_240m
def test_shackleton_floor_is_walled_in_between_19_5_and_24_deg():
    x, y = latlon_to_xy(*SHACKLETON)
    H = skyline(single(read_polar_dem(LOLA)), x, y, 2.0)[0]
    assert 19.5 < H.min() and H.max() < 24.0          # 19.75-23.52 deg; the Sun never tops ~1.6: permanent shadow


@needs_20m
def test_rim_site_is_dark_at_2_m_and_the_crest_103_m_away_is_lit():
    x0, y0 = latlon_to_xy(*RIM_SITE)
    fine = read_polar_dem(LOLA_20M, fine_bounds(np.array([x0]), np.array([y0]), D_FINE))
    # the crest: highest 20 m pixel within 250 m of the rim site (+9.25 m at 103.0 m)
    row0, col0 = fine.xy_to_rowcol(x0, y0)
    rr, cc = np.mgrid[int(row0) - 15:int(row0) + 16, int(col0) - 15:int(col0) + 16]
    xs, ys = fine.rowcol_to_xy(rr.astype(float), cc.astype(float))
    within = np.hypot(xs - x0, ys - y0) <= 250
    k = np.argmax(np.where(within, fine.height[rr, cc], -np.inf))
    xc, yc = xs.flat[k], ys.flat[k]
    ground = float(bilinear(fine.height, np.array(col0), np.array(row0)))
    assert 100 < np.hypot(xc - x0, yc - y0) < 106 and 8.5 < fine.height[rr, cc].flat[k] - ground < 10.0

    xs, ys = np.array([x0, xc]), np.array([y0, yc])
    sun, _ = visibility(skyline(near_field(xs, ys), xs, ys, 2.0), xs, ys)
    assert sun[0] < 0.02                               # rim site: 0.3%
    assert 0.80 < sun[1] < 0.92                        # crest: 85.9%
