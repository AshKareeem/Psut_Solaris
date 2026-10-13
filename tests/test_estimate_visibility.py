import numpy as np
import pytest

from scripts.estimate_visibility import earth_fraction, sun_fraction, tilt

THETA = np.arange(1440) * 0.25


def test_sun_on_a_level_skyline_is_half_the_time():
    """The yearly sine is symmetric about level, so a flat 0 deg skyline gives exactly 50%."""
    assert sun_fraction(np.zeros_like(THETA), THETA, 0.0, 0.0) == pytest.approx(0.5)


def test_earth_on_the_rim_site_skyline():
    """Skyline -0.57 deg toward Earth, disc 0.95 deg, libration 6.7 deg: 0.5 + asin(1.52/6.7)/pi."""
    assert earth_fraction(np.full_like(THETA, -0.57), THETA, 0.0, 0.0) == pytest.approx(0.5729, abs=1e-4)


def test_tilt_direction_follows_the_map_convention():
    c, theta_out = tilt(-89.0, 0.0)  # 1 deg from the pole toward longitude 0 = map up
    assert c == pytest.approx(1.0) and theta_out == pytest.approx(90.0)
    assert tilt(-89.0, 90.0)[1] == pytest.approx(0.0)  # toward 90E = map right


def test_site_toward_earth_sees_earth_more():
    H = np.full_like(THETA, -0.57)
    assert earth_fraction(H, THETA, 1.0, 90.0) > earth_fraction(H, THETA, 0.0, 0.0) > earth_fraction(H, THETA, 1.0, 270.0)
