import numpy as np
import pytest

from horizon.fast import horizon_profiles_fast
from horizon.reference import horizon_profile
from horizon.synthetic import bowl_crater, cone, distance_grid

PIXEL = 20.0
N = 1501


def terrain():
    crater = bowl_crater(distance_grid(N, PIXEL, 700, 760), radius=5000.0, depth=2000.0, rim=400.0)
    return (crater + cone(distance_grid(N, PIXEL, 300, 300), peak=1500.0, base_radius=4000.0)).astype(np.float32)


def test_fast_matches_reference():
    dem = terrain()
    rng = np.random.default_rng(0)
    cols, rows = rng.uniform(600, 900, 8), rng.uniform(600, 900, 8)
    try:
        H, D, ok = horizon_profiles_fast(dem, PIXEL, cols, rows, mast=2.0, d_max=12_000, n_az=720, kappa=0.002)
    except NotImplementedError:
        pytest.skip("horizon/fast.py not implemented yet (week 2)")
    for s in range(len(cols)):
        H_ref, D_ref, ok_ref = horizon_profile(dem, PIXEL, cols[s], rows[s], 2.0, 12_000, n_az=720, kappa=0.002)
        assert np.abs(H[s] - H_ref).max() < 1e-6
        assert np.array_equal(D[s], D_ref) and np.array_equal(ok[s], ok_ref)
