import numpy as np

from scripts.battery import Battery, levels, simulate
from scripts.score_sites import best_dates, date_metrics, longest_run, recommended_mast, skyline_at, visibility

WEIGHTS = {"sun": 0.30, "earth": 0.20, "both": 0.35, "gap": 0.15}


def test_battery_matches_iots_examples():
    b = Battery()
    assert b.bridge_hours() == 11.2
    lowest, death = simulate(np.array([0.0] * 11 + [1.0] * 20), b)   # 11 dark hours: 700 - 550 = 150 Wh, survives
    assert death == -1 and lowest == 150.0
    lowest, death = simulate(np.array([0.0] * 14 + [1.0] * 10), b)   # after 12 dark hours it is at 100 Wh
    assert death == 11 and lowest == 0.0
    assert min(levels(np.array([0.0] * 14 + [1.0] * 10), b)) == lowest


def test_skyline_is_interpolated_between_directions_and_wraps():
    H = np.array([[0.0, 1.0, 2.0, 3.0]])                    # 4 directions, 90 deg apart
    assert np.allclose(skyline_at(H, np.array([[45.0, 315.0, 360.0]])), [[0.5, 1.5, 0.0]])


def test_visibility_uses_the_team_formulas_and_each_hours_radii():
    H = np.zeros((1, 1, 4))                                 # flat skyline at 0 deg, one site, one mast
    sky = {"sun_az": np.full((1, 3), 10.0), "earth_az": np.full((1, 3), 90.0),
           "sun_el": np.array([[-0.27, 0.0, 0.27]]), "earth_el": np.array([[-0.95, -0.94, 0.0]]),
           "sun_radius_deg": np.full(3, 0.27), "earth_radius_deg": np.full(3, 0.95)}
    s, e, b = visibility(H, sky)
    assert np.allclose(s[0, 0], [0.0, 0.5, 1.0])            # disc below / half / fully above
    assert e[0, 0].tolist() == [False, True, True]          # any part of Earth above the skyline
    assert b[0, 0].tolist() == [False, False, True]         # needs more than half the Sun


def test_metrics_per_landing_date_and_longest_dark_run():
    assert longest_run(np.array([True, True, False, True, True, True, False])) == 3
    hours = 48                                              # a 2-day mission, 3 days of data: 2 landing dates
    s = np.zeros((1, 1, 72), np.float32)
    s[..., 24:] = 1.0                                       # dark on day 1, lit after
    e = np.ones_like(s, bool)
    met = date_metrics(s, e, (s > 0.5) & e, hours, WEIGHTS, Battery())
    assert np.allclose(met["f_sun"][0, 0], [0.5, 1.0])
    assert met["gap_h"][0, 0].tolist() == [24, 0]
    assert met["death_h"][0, 0].tolist() == [11, -1]        # 24 dark hours kill it on the first date only


def test_best_date_prefers_surviving_dates_and_mast_rule():
    score = np.array([[[0.9, 0.5, 0.6]]])                   # 1 site, 1 mast, 3 dates
    survives = np.array([[[False, True, True]]])
    assert best_dates(score, survives, 2)[:, 0, 0].tolist() == [2, 1]
    best = np.array([[0.80, 0.86, 0.90]])                   # masts 0, 2, 5 m: 2 m is within 0.05 of the best
    assert recommended_mast(best, np.array([[True, True, True]]), [0.0, 2.0, 5.0], 0.05)[0] == 2.0
    assert np.isnan(recommended_mast(best, np.array([[False, False, False]]), [0.0, 2.0, 5.0], 0.05)[0])
