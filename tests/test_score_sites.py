import numpy as np

from scripts.battery import Battery, levels, simulate, simulate_windows
from scripts.events import skyline_at
from scripts.score_sites import (battery_needed, best_dates, date_metrics, neighbour_safe, ranking, recommended_mast, safe_days,
                                 visibility, window_longest_run, window_sum)


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


def sky_flat(sun_el, earth_el):
    n = len(sun_el)
    return {"sun_az": np.full((1, n), 10.0), "earth_az": np.full((1, n), 90.0),
            "sun_el": np.array([sun_el]), "earth_el": np.array([earth_el]),
            "sun_radius_deg": np.full(n, 0.27), "earth_radius_deg": np.full(n, 0.95)}


def test_visibility_uses_the_team_formulas_each_hours_radii_and_the_earth_margin():
    H = np.zeros((1, 1, 4))                                 # flat skyline at 0 deg, one site, one mast
    s, e, b = visibility(H, sky_flat([-0.27, 0.0, 0.27], [-0.95, -0.94, 0.0]), 0.0)
    assert np.allclose(s[0, 0], [0.0, 0.5, 1.0])            # disc below / half / fully above
    assert e[0, 0].tolist() == [False, True, True]          # any part of Earth above the skyline
    assert b[0, 0].tolist() == [False, False, True]         # needs more than half the Sun
    _, e, _ = visibility(H, sky_flat([0.0] * 3, [-0.94, 0.0, 1.0]), 1.0)
    assert e[0, 0].tolist() == [False, False, True]         # an antenna needing 1 deg of clearance


def test_metrics_per_landing_hour_touchdown_and_longest_dark_run():
    hours = 48                                              # a 2-day mission, 3 days of data: 25 landing hours
    s = np.zeros((1, 1, 72), np.float32)
    s[..., 24:] = 1.0                                       # dark on day 1, lit after
    e = np.ones_like(s, bool)
    met = date_metrics(s, e, (s > 0.5) & e, hours, Battery(), 0.5)
    assert met["safe"].shape == (1, 1, 25)
    assert met["n_sun"][0, 0, [0, 12, 24]].tolist() == [24, 36, 48]
    assert met["gap_h"][0, 0, [0, 12, 24]].tolist() == [24, 12, 0]
    assert met["death_h"][0, 0, [0, 12, 24]].tolist() == [11, 11, -1]   # 12 or more dark hours kill it
    assert met["touchdown"][0, 0].tolist() == [False] * 24 + [True]
    assert met["safe"][0, 0].tolist() == [False] * 24 + [True]


def test_windowed_metrics_match_each_mission_computed_on_its_own():
    rng = np.random.default_rng(1)
    sun = rng.choice([0.0, 0.3, 0.6, 1.0], size=(3, 200))
    hours, b = 50, Battery()
    lowest, death = simulate_windows(sun, hours, b)
    runs = window_longest_run(sun < 0.5, hours)
    sums = window_sum(sun > 0.5, hours)
    for i in range(3):
        for k in range(0, 151, 7):
            w = sun[i, k:k + hours]
            lo, de = simulate(w, b)
            assert abs(lowest[i, k] - lo) < 1e-3 and death[i, k] == de
            dark = "".join("1" if v < 0.5 else "0" for v in w)
            assert runs[i, k] == max(len(x) for x in dark.split("0")) and sums[i, k] == (w > 0.5).sum()


def test_a_sky_whose_only_safe_touchdown_is_1300_gives_one_safe_day():
    """Council R7: landing only at 00:00 UTC missed every day whose safe touchdown is later in the day."""
    hours = 24
    s = np.full((1, 1, 48), 0.4, np.float32)                # under half the Sun, yet 80 W > 50 W: it charges
    s[..., 13] = 1.0                                        # power at touchdown only at 13:00 on day 1
    e = np.ones_like(s, bool)
    met = date_metrics(s, e, (s > 0.5) & e, hours, Battery(), 0.5)
    assert np.flatnonzero(met["safe"][0, 0]).tolist() == [13]
    assert safe_days(met["safe"])[0, 0] == 1
    assert best_dates(met, hours, 1)[0, 0, 0] == 13


def test_a_date_that_dies_is_never_a_best_date():
    """Finding C: 312 of 400 demo sites reported a 'best landing date' on which the lander died by hour 11."""
    s = np.zeros((1, 1, 48), np.float32)
    s[..., :2] = 1.0                                        # lit at touchdown, then dark for good
    e = np.ones_like(s, bool)
    met = date_metrics(s, e, (s > 0.5) & e, 24, Battery(), 0.5)
    assert met["touchdown"][0, 0, 0] and not met["safe"].any()
    order = best_dates(met, 24, 2)
    assert not met["safe"][0, 0, order[:, 0, 0]].any()      # no safe date to list
    assert np.isnan(recommended_mast(met["safe"].sum(-1), [0.0])[0])


def test_best_dates_are_the_best_hour_of_the_best_days():
    """Most power and Earth together, then the shortest darkness, then the earliest; one entry per day."""
    safe, both, gap = np.zeros((1, 1, 72), bool), np.zeros((1, 1, 72), np.int16), np.zeros((1, 1, 72), np.int16)
    safe[..., [2, 5, 30, 50, 60]] = True
    both[..., [0, 2, 5, 30, 50, 60]] = [99, 10, 10, 12, 12, 12]   # hour 0 is not safe: never listed
    gap[..., [2, 5, 30, 50, 60]] = [4, 0, 5, 3, 3]                 # hour 5 beats hour 2 on darkness
    met = {"safe": safe, "n_both": both, "gap_h": gap}
    assert best_dates(met, 24, 3)[:, 0, 0].tolist() == [50, 30, 5]  # day 3 (earliest of 50, 60), day 2, day 1 (hour 5)


def test_ranking_per_mast_by_safe_days_then_battery_needed():
    """Council R1: a list per mast, so a site with 499 safe days at 10 m is never ranked below one with 4 days just
    because it needs a taller mast. Ties: less battery needed, then sites.csv order."""
    days = np.zeros(300)
    days[[190, 210, 33, 13]] = [4, 499, 49, 49]
    bridge = np.zeros(300)
    bridge[[33, 13]] = [600.0, 300.0]
    assert ranking([190, 210, 33, 13], days, bridge) == [210, 13, 33, 190]
    assert np.isnan(recommended_mast(np.zeros((1, 4), int), [0.0, 2.0, 5.0, 10.0])[0])
    assert recommended_mast(np.array([[0, 0, 0, 192]]), [0.0, 2.0, 5.0, 10.0])[0] == 10.0


def test_battery_needed_counts_partial_sun_and_never_exceeds_what_a_safe_landing_can_use():
    """Council R6: darkness x load overstated it (44 demo cases above the 560 Wh the battery can give, yet alive)."""
    s = np.ones((1, 1, 48), np.float32)
    s[..., 4:14] = 0.0                                      # 10 dark hours: 500 Wh at 50 W
    s[..., 14:18] = 0.4                                     # under half the Sun: still dark, but 80 W > 50 W charges
    e = np.ones_like(s, bool)
    b = Battery()
    met = date_metrics(s, e, (s > 0.5) & e, 24, b, 0.5)
    need = battery_needed(met, b.e_max)[0, 0]
    assert met["gap_h"][0, 0, 0] == 14 and need == 500.0    # 14 dark hours x 50 W = 700 Wh would be wrong
    assert need <= b.e_max - b.e_min
    assert np.isnan(battery_needed({"safe": np.zeros((1, 1, 3), bool), "lowest_Wh": np.zeros((1, 1, 3))}, 700.0)[0, 0])


def test_a_date_with_earth_in_view_for_too_little_of_the_mission_is_not_safe():
    """Council R2: NASA's reference is direct-with-Earth communication, no relay. Touchdown in Sun and Earth and a
    living battery are not enough if Earth is hidden for most of the mission."""
    s = np.ones((1, 1, 48), np.float32)                     # full Sun all the time: the battery never drains
    e = np.zeros_like(s, bool)
    e[..., :6] = True                                       # Earth in view at touchdown, then hidden: 6 of 24 h
    met = date_metrics(s, e, (s > 0.5) & e, 24, Battery(), 0.5)
    assert met["touchdown"][0, 0, 0] and met["death_h"][0, 0, 0] < 0
    assert not met["safe"][0, 0, 0]
    assert date_metrics(s, e, (s > 0.5) & e, 24, Battery(), 0.25)["safe"][0, 0, 0]   # 6/24 meets a 25% rule


def test_a_date_counts_within_100_m_only_if_safe_at_every_point(tmp_path):
    hours = 72
    sun_az = np.where(np.arange(hours) < 24, 10.0, 190.0)[None]       # day 1 toward theta 10, then toward 190
    sky = {"sun_az": sun_az, "sun_el": np.ones((1, hours)), "earth_az": np.full((1, hours), 90.0),
           "earth_el": np.full((1, hours), 2.0), "sun_radius_deg": np.full(hours, 0.27),
           "earth_radius_deg": np.full(hours, 0.95)}
    H_parent = np.zeros((1, 1, 4))
    H_points = np.zeros((2, 1, 4))
    H_points[1, 0, 0] = 5.0                                  # a ridge toward theta 0 at the second point
    np.save(tmp_path / "horizon.npy", H_points)
    np.save(tmp_path / "complete.npy", np.ones((2, 1, 4), bool))
    parent_safe = date_metrics(*visibility(H_parent, sky, 0.0), 24, Battery(), 0.5)["safe"]
    assert parent_safe[0, 0].all() and parent_safe.shape == (1, 1, 49)
    safe_100m, complete, n_points = neighbour_safe(tmp_path, sky, 24, Battery(), 0.0, 0.5, np.array([0, 0]),
                                                   parent_safe)
    assert safe_100m[0, 0].tolist() == [False] * 24 + [True] * 25   # the ridge hides touchdown on day 1
    assert complete[0, 0] and n_points.tolist() == [2]
