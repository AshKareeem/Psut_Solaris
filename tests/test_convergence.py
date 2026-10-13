import numpy as np

from scripts.convergence import between_rays


def test_between_rays_keeps_shared_rays_and_wraps_around():
    H = np.array([[0.0, 9.0, 2.0, 9.0, 4.0, 9.0, 6.0, 9.0]])
    # keeps rays 0, 2, 4, 6; ray 7 lies between ray 6 and ray 0 (across 360 deg)
    assert np.array_equal(between_rays(H, 2), [[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 3.0]])
