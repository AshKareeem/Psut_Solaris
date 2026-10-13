from pathlib import Path

import numpy as np
import pytest

from horizon.dem import read_polar_dem
from horizon.fast import horizon_profiles_fast
from horizon.reference import horizon_profile
from horizon.synthetic import bowl_crater, cone, distance_grid

PIXEL = 20.0
N = 1501
LOLA = Path(__file__).resolve().parents[1] / "data" / "ldem_75s_240m.lbl"


def terrain():
    crater = bowl_crater(distance_grid(N, PIXEL, 700, 760), radius=5000.0, depth=2000.0, rim=400.0)
    return (crater + cone(distance_grid(N, PIXEL, 300, 300), peak=1500.0, base_radius=4000.0)).astype(np.float32)


def assert_matches_reference(dem, pixel, cols, rows, mast, d_max, n_az, kappa):
    H, D, ok = horizon_profiles_fast(dem, pixel, cols, rows, mast, d_max, n_az, kappa)
    for s in range(len(cols)):
        H_ref, D_ref, ok_ref = horizon_profile(dem, pixel, cols[s], rows[s], mast, d_max, n_az, kappa)
        assert np.abs(H[s] - H_ref).max() < 1e-6
        assert np.array_equal(D[s], D_ref) and np.array_equal(ok[s], ok_ref)


def test_fast_matches_reference():
    rng = np.random.default_rng(0)
    cols, rows = rng.uniform(600, 900, 8), rng.uniform(600, 900, 8)
    assert_matches_reference(terrain(), PIXEL, cols, rows, mast=2.0, d_max=12_000, n_az=720, kappa=0.002)


def test_fast_flags_rays_leaving_the_map_like_the_reference():
    cols, rows = np.array([100.0, 1400.0]), np.array([750.0, 200.0])  # near the edges: some rays leave
    assert_matches_reference(terrain(), PIXEL, cols, rows, mast=2.0, d_max=12_000, n_az=360, kappa=0.002)


def test_fast_site_off_the_map_fails_fast():
    with pytest.raises(ValueError, match=r"sites \[1\] are off the map"):
        horizon_profiles_fast(terrain(), PIXEL, np.array([750.0, 5000.0]), np.array([750.0, 750.0]),
                              mast=2.0, d_max=1_000)


@pytest.mark.skipif(not LOLA.exists(), reason="needs data/ldem_75s_240m.lbl")
def test_fast_matches_reference_on_lola():
    """Shackleton rim, Shackleton floor and a site 1.5 deg from the pole, on real 240 m terrain."""
    dem = read_polar_dem(LOLA)
    rows, cols = dem.latlon_to_rowcol(np.array([-89.779, -89.67, -88.5]), np.array([-155.73, 129.78, 45.0]))
    assert_matches_reference(dem.height, dem.pixel, cols, rows, mast=2.0, d_max=150_000, n_az=720, kappa=0.002)
