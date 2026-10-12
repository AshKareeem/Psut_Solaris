import numpy as np

from horizon.reference import R, horizon_profile
from horizon.synthetic import cone, distance_grid, ring

PIXEL = 20.0
N = 2001
C = N // 2  # site at the centre


def exact_angle(peak, distance):
    return np.degrees(np.arctan2((R + peak) * np.cos(distance / R) - R, (R + peak) * np.sin(distance / R)))


def test_smooth_moon_dips_equally_everywhere():
    H, D, ok = horizon_profile(np.zeros((N, N)), PIXEL, C, C, mast=2.0, d_max=15_000)
    expected = -np.degrees(np.arccos(R / (R + 2.0)))  # -0.0869 deg
    assert np.allclose(H, expected, atol=1e-4)
    assert abs(np.median(D) - np.sqrt(2 * R * 2.0)) < 50  # blocked at the tangent distance
    assert ok.all()


def test_single_cone_exact_angle_and_distance():
    dem = cone(distance_grid(N, PIXEL, C, C + 500), peak=1000.0, base_radius=3000.0)  # 10 km along +x
    H, D, ok = horizon_profile(dem, PIXEL, C, C, mast=0.0, d_max=15_000)
    assert abs(H[0] - exact_angle(1000.0, 10_000.0)) < 1e-6
    assert D[0] == 10_000.0


def test_ring_crater_same_in_every_direction():
    dem = ring(distance_grid(N, PIXEL, C, C), peak=1000.0, radius=10_000.0, half_width=3000.0)
    H, D, ok = horizon_profile(dem, PIXEL, C, C, mast=0.0, d_max=15_000)
    # bilinear interpolation shaves sharp crests between grid points: up to ~0.017 deg here
    assert np.abs(H - exact_angle(1000.0, 10_000.0)).max() < 0.02


def test_ray_leaving_the_map_is_flagged():
    H, D, ok = horizon_profile(np.zeros((201, 201)), PIXEL, 100, 100, mast=2.0, d_max=15_000)
    assert not ok.any()
