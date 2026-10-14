from pathlib import Path

import numpy as np
import pytest

from horizon import D_FINE, D_MAX, KAPPA, N_AZ
from horizon.dem import PolarDEM, latlon_to_xy, read_polar_dem
from horizon.fast import horizon_profiles_fast
from horizon.reference import horizon_profile
from horizon.sites import RIM_SITE
from horizon.synthetic import bowl_crater, cone, distance_grid
from horizon.terrain import fine_bounds, multires, single

PIXEL = 20.0
N = 1501
LOLA = Path(__file__).resolve().parents[1] / "data" / "ldem_75s_240m.lbl"
LOLA_20M = LOLA.with_name("ldem_875s_20m.lbl")


def terrain():
    crater = bowl_crater(distance_grid(N, PIXEL, 700, 760), radius=5000.0, depth=2000.0, rim=400.0)
    return (crater + cone(distance_grid(N, PIXEL, 300, 300), peak=1500.0, base_radius=4000.0)).astype(np.float32)


def grid(height, pixel=PIXEL, pole=750.0):
    return PolarDEM(height=height, pixel=pixel, pole_row=pole, pole_col=pole)


def block_mean(dem, f):
    """The same terrain f times coarser, the way LOLA's coarser maps relate to the finer ones."""
    n = dem.height.shape[0] // f * f
    h = dem.height[:n, :n].reshape(n // f, f, n // f, f).mean(axis=(1, 3))
    return PolarDEM(height=h, pixel=dem.pixel * f, pole_row=(dem.pole_row - (f - 1) / 2) / f,
                    pole_col=(dem.pole_col - (f - 1) / 2) / f)


def sites(rows, cols):
    """Map x, y of grid positions on the test terrain."""
    return grid(np.zeros((1, 1))).rowcol_to_xy(np.asarray(rows, float), np.asarray(cols, float))


def assert_matches_reference(ter, xs, ys, mast, d_max, n_az, kappa):
    H, D, ok = horizon_profiles_fast(ter, xs, ys, mast, d_max, n_az, kappa)
    for s in range(len(xs)):
        H_ref, D_ref, ok_ref = horizon_profile(ter, xs[s], ys[s], mast, d_max, n_az, kappa)
        assert np.abs(H[s] - H_ref).max() < 1e-6
        assert np.array_equal(D[s], D_ref) and np.array_equal(ok[s], ok_ref)


def test_fast_matches_reference():
    rng = np.random.default_rng(0)
    cols, rows = rng.uniform(600, 900, 8), rng.uniform(600, 900, 8)
    xs, ys = sites(rows, cols)
    assert_matches_reference(single(grid(terrain())), xs, ys, mast=2.0, d_max=12_000, n_az=720, kappa=0.002)


def test_fast_flags_rays_leaving_the_map_like_the_reference():
    xs, ys = sites([750.0, 200.0], [100.0, 1400.0])  # near the edges: some rays leave
    assert_matches_reference(single(grid(terrain())), xs, ys, mast=2.0, d_max=12_000, n_az=360, kappa=0.002)


def test_fast_skips_no_data_holes_like_the_reference():
    dem = terrain()
    dem[500:540, 500:900] = np.nan  # a band that many rays cross
    dem[1450:, :] = np.nan          # and the bottom edge, where rays end: those must be incomplete
    xs, ys = sites([650.0, 800.0, 1300.0], [700.0, 820.0, 650.0])
    assert_matches_reference(single(grid(dem)), xs, ys, mast=2.0, d_max=12_000, n_az=720, kappa=0.002)


def test_fast_matches_reference_on_two_levels():
    """20 m terrain near the sites, a 4x coarser map from 3 km on; rays run off the coarse map's edge too."""
    fine = grid(terrain())
    xs, ys = sites([700.0, 760.0, 820.0], [700.0, 640.0, 790.0])
    assert_matches_reference(multires(fine, block_mean(fine, 4), 3000.0), xs, ys, 2.0, 18_000, 720, 0.002)


def test_splitting_one_map_into_levels_changes_nothing():
    dem = grid(terrain())
    xs, ys = sites([700.0, 820.0], [700.0, 790.0])
    H1, D1, ok1 = horizon_profiles_fast(single(dem), xs, ys, 2.0, 12_000, 720, 0.002)
    H2, D2, ok2 = horizon_profiles_fast(multires(dem, dem, 4000.0), xs, ys, 2.0, 12_000, 720, 0.002)
    assert np.array_equal(H1, H2) and np.array_equal(D1, D2) and np.array_equal(ok1, ok2)
    H_ref, _, _ = horizon_profile(multires(dem, dem, 4000.0), xs[0], ys[0], 2.0, 12_000, 720, 0.002)
    assert np.array_equal(H_ref, H1[0])


def test_fine_terrain_that_does_not_reach_far_enough_fails_fast():
    fine = PolarDEM(height=terrain()[600:900, 600:900], pixel=PIXEL, pole_row=150.0, pole_col=150.0)  # +-3 km
    coarse = block_mean(grid(terrain()), 4)
    with pytest.raises(ValueError, match=r"the 20 m terrain does not reach 5.0 km"):
        horizon_profiles_fast(multires(fine, coarse, 5000.0), np.array([0.0]), np.array([0.0]), 2.0, 12_000, 720, 0.002)


def test_fast_site_off_the_map_fails_fast():
    with pytest.raises(ValueError, match=r"sites \[1\] are off the map"):
        horizon_profiles_fast(single(grid(terrain())), *sites([750.0, 750.0], [750.0, 5000.0]), mast=2.0, d_max=1_000,
                              n_az=360, kappa=0.002)


@pytest.mark.skipif(not LOLA.exists(), reason="needs data/ldem_75s_240m.lbl")
def test_fast_matches_reference_on_lola():
    """Shackleton rim, Shackleton floor and a site 1.5 deg from the pole, on real 240 m terrain."""
    xs, ys = latlon_to_xy(np.array([-89.779, -89.67, -88.5]), np.array([-155.73, 129.78, 45.0]))
    assert_matches_reference(single(read_polar_dem(LOLA)), xs, ys, mast=2.0, d_max=150_000, n_az=720, kappa=0.002)


@pytest.mark.skipif(not (LOLA.exists() and LOLA_20M.exists()), reason="needs data/ldem_75s_240m and ldem_875s_20m")
def test_fast_matches_reference_on_lola_20m_and_240m():
    """Shackleton rim and floor on 20 m terrain within D_FINE and the 240 m map beyond, at the final settings."""
    xs, ys = latlon_to_xy(np.array([RIM_SITE[0], -89.67]), np.array([RIM_SITE[1], 129.78]))
    terrain = multires(read_polar_dem(LOLA_20M, fine_bounds(xs, ys, D_FINE)), read_polar_dem(LOLA), D_FINE)
    assert_matches_reference(terrain, xs, ys, mast=2.0, d_max=D_MAX, n_az=N_AZ, kappa=KAPPA)
