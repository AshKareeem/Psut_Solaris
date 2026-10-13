import numpy as np
import pytest

from horizon.dem import PolarDEM
from horizon.reference import R, horizon_profile
from horizon.synthetic import cone, distance_grid, ring
from horizon.terrain import single

PIXEL = 20.0
N = 2001
C = N // 2  # site at the centre


def centred(height):
    """One-level terrain with the pole, and the site (x = y = 0), at the centre of the grid."""
    c = (height.shape[0] - 1) / 2
    return single(PolarDEM(height=height, pixel=PIXEL, pole_row=c, pole_col=c))


def exact_angle(peak, distance):
    return np.degrees(np.arctan2((R + peak) * np.cos(distance / R) - R, (R + peak) * np.sin(distance / R)))


def test_smooth_moon_dips_equally_everywhere():
    H, D, ok = horizon_profile(centred(np.zeros((N, N))), 0.0, 0.0, mast=2.0, d_max=15_000)
    expected = -np.degrees(np.arccos(R / (R + 2.0)))  # -0.0869 deg
    assert np.allclose(H, expected, atol=1e-4)
    assert abs(np.median(D) - np.sqrt(2 * R * 2.0)) < 50  # blocked at the tangent distance
    assert ok.all()


def test_single_cone_exact_angle_and_distance():
    dem = cone(distance_grid(N, PIXEL, C, C + 500), peak=1000.0, base_radius=3000.0)  # 10 km along +x
    H, D, ok = horizon_profile(centred(dem), 0.0, 0.0, mast=0.0, d_max=15_000)
    assert abs(H[0] - exact_angle(1000.0, 10_000.0)) < 1e-6
    assert D[0] == 10_000.0


def test_ring_crater_same_in_every_direction():
    dem = ring(distance_grid(N, PIXEL, C, C), peak=1000.0, radius=10_000.0, half_width=3000.0)
    H, D, ok = horizon_profile(centred(dem), 0.0, 0.0, mast=0.0, d_max=15_000)
    # bilinear interpolation shaves sharp crests between grid points: up to ~0.017 deg here
    assert np.abs(H - exact_angle(1000.0, 10_000.0)).max() < 0.02


def test_ray_leaving_the_map_is_flagged():
    H, D, ok = horizon_profile(centred(np.zeros((201, 201))), 0.0, 0.0, mast=2.0, d_max=15_000)
    assert not ok.any()


def test_site_off_the_map_fails_fast():
    with pytest.raises(ValueError, match="off the map"):
        horizon_profile(centred(np.zeros((201, 201))), 8000.0, 0.0, mast=2.0, d_max=1_000)  # 400 px east
