import numpy as np

from horizon.dem import PolarDEM
from scripts.battery import Battery
from scripts.named_to_sites import height_and_slope


def test_slope_over_100_m_on_a_tilted_plane():
    n, pixel = 201, 20.0
    rr, cc = np.mgrid[0:n, 0:n]
    x, y = (cc - 100) * pixel, (100 - rr) * pixel
    plane = (0.1 * x + 0.05 * y + 500.0).astype(np.float32)        # rises 0.1 m per m east, 0.05 m per m north
    dem = PolarDEM(height=plane, pixel=pixel, pole_row=100.0, pole_col=100.0)
    height, slope = height_and_slope(dem, 300.0, -200.0)
    assert abs(height - (0.1 * 300 - 0.05 * 200 + 500)) < 1e-3
    assert abs(slope - np.degrees(np.arctan(np.hypot(0.1, 0.05)))) < 1e-6


def test_lander_profile_states_its_numbers_and_sources():
    p = Battery().profile()
    assert (p["e_max_Wh"], p["e_min_Wh"], p["p_panel_W"], p["p_load_W"], p["bridge_hours"]) == (700, 140, 200, 50, 11.2)
    assert "upper bound" in p["model"] and set(p["sources"]) == {"p_panel", "e_max", "p_load", "e_min"}
