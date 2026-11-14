import numpy as np

from scripts.battery import Battery, levels, simulate, simulate_windows
from scripts.events import skyline_at
from scripts.score_sites import (battery_needed, best_dates, consecutive_safe, delay_ladder, firm_touchdown,
                                 miss_table, rank_reasons, ranking_keys, risk_words, date_metrics, neighbour_safe,
                                 ranking, recommended_mast, safe_days, visibility, window_longest_run, window_sum)


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
    assert best_dates(met, np.ones_like(met['safe']), hours, 1)[0, 0, 0] == 13


def test_a_date_that_dies_is_never_a_best_date():
    """Finding C: 312 of 400 demo sites reported a 'best landing date' on which the lander died by hour 11."""
    s = np.zeros((1, 1, 48), np.float32)
    s[..., :2] = 1.0                                        # lit at touchdown, then dark for good
    e = np.ones_like(s, bool)
    met = date_metrics(s, e, (s > 0.5) & e, 24, Battery(), 0.5)
    assert met["touchdown"][0, 0, 0] and not met["safe"].any()
    order = best_dates(met, np.ones_like(met['safe']), 24, 2)
    assert not met["safe"][0, 0, order[:, 0, 0]].any()      # no safe date to list
    assert np.isnan(recommended_mast(met["safe"].sum(-1), [0.0])[0])


def test_best_dates_are_the_best_hour_of_the_best_days():
    """Most power and Earth together, then the shortest darkness, then the earliest; one entry per day."""
    safe, both, gap = np.zeros((1, 1, 72), bool), np.zeros((1, 1, 72), np.int16), np.zeros((1, 1, 72), np.int16)
    safe[..., [2, 5, 30, 50, 60]] = True
    both[..., [0, 2, 5, 30, 50, 60]] = [99, 10, 10, 12, 12, 12]   # hour 0 is not safe: never listed
    gap[..., [2, 5, 30, 50, 60]] = [4, 0, 5, 3, 3]                 # hour 5 beats hour 2 on darkness
    met = {"safe": safe, "n_both": both, "gap_h": gap}
    firm = np.ones_like(safe)
    assert best_dates(met, firm, 24, 3)[:, 0, 0].tolist() == [50, 30, 5]  # day 3 (earliest of 50, 60), day 2, day 1 (hour 5)


def test_a_firm_touchdown_beats_a_marginal_one_with_more_hours():
    """Risk review Nov 13: 36 of 39 headline landings were marginal, because ties went to the earliest hour, when Earth
    is just rising. A firm touchdown (both bodies at least 0.5 deg clear) now comes first; days are still ranked."""
    safe, both, gap = np.zeros((1, 1, 48), bool), np.zeros((1, 1, 48), np.int16), np.zeros((1, 1, 48), np.int16)
    safe[..., [3, 9, 30]] = True
    both[..., [3, 9, 30]] = [20, 15, 20]
    firm = np.zeros_like(safe)
    firm[..., 9] = True                                       # hour 3 has more hours together but is marginal
    met = {"safe": safe, "n_both": both, "gap_h": gap}
    assert best_dates(met, firm, 24, 2)[:, 0, 0].tolist() == [9, 30]   # day 1 picks the firm hour and ranks first


def test_firm_touchdown_needs_both_bodies_half_a_degree_clear():
    H = np.zeros((1, 1, 360))
    firm = firm_touchdown(H, sky_flat([0.4, 0.6, 0.6], [0.0, 0.0, -0.5]), 0.0)
    assert firm[0, 0].tolist() == [False, True, False]        # Sun 0.4 deg up; both clear; Earth's top 0.45 deg up


def test_ranking_per_mast_by_safe_days_then_battery_needed():
    """Council R1: a list per mast, so a site with 499 safe days at 10 m is never ranked below one with 4 days just
    because it needs a taller mast. Ties: less battery needed, then sites.csv order."""
    days = np.zeros(300)
    days[[190, 210, 33, 13]] = [4, 499, 49, 49]
    bridge = np.zeros(300)
    bridge[[33, 13]] = [600.0, 300.0]
    assert ranking([190, 210, 33, 13], days, days, bridge) == [210, 13, 33, 190]
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


def test_sites_with_no_safe_day_within_100_m_stay_listed_by_their_days_on_target():
    """Council R8: dropping them left the 2 m demo list with one site."""
    within, on_target, need = np.array([18.0, 0, 0, 0]), np.array([79, 91, 219, 190]), np.full(4, 558.0)
    assert ranking([0, 1, 2, 3], within, on_target, need) == [0, 2, 3, 1]


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
                                                   parent_safe, np.array([False, False]))
    assert safe_100m[0, 0].tolist() == [False] * 24 + [True] * 25   # the ridge hides touchdown on day 1
    assert complete[0, 0] and n_points.tolist() == [2]
    # council R3, option A: one point within 100 m too steep to land on, and no date is safe within 100 m
    steep, _, _ = neighbour_safe(tmp_path, sky, 24, Battery(), 0.0, 0.5, np.array([0, 0]), parent_safe,
                                 np.array([False, True]))
    assert not steep.any()


def test_rank_reasons_name_the_metric_that_decides_each_place():
    ids = np.array(["a", "b", "c", "d"])
    values = {"safe_days_within_100m": np.array([18.0, 0.0, 0.0, 0.0]),
              "safe_landing_days": np.array([79.0, 219.0, 219.0, 92.0]),
              "battery_needed_Wh": np.array([558.0, 300.0, 300.0, np.nan])}
    r = rank_reasons([0, 1, 2, 3], values, ids, ranking_keys(True))
    assert r[0] == ("#1 of 4. Ahead of #2 (site b): safe landing days if the lander misses by up to 100 m: 18 vs 0.")
    assert "Ahead of #3 (site c): every metric ties; listed by site order." in r[1]
    assert "Ahead of #4 (site d): safe landing days on the exact point: 219 vs 92." in r[2]
    assert r[3].endswith("Behind #3 (site c): safe landing days on the exact point: 219 vs 92.")
    assert [k[0] for k in ranking_keys(False)] == ["safe_landing_days", "battery_needed_Wh"]


def test_delay_margin_and_ladder_count_safe_hours_after_the_headline():
    """Spec commit 1: safe hours k = 3, 4, 5, 6 and 30, headline k = 3. Counted by hand: hours 3-6 are 4 consecutive
    safe hours (so land up to 3 h late); a 1 h slip (k = 4) is safe; a 6 h slip (k = 9) is not and the first safe
    hour at or after it is k = 30 = 2026-01-02T06; so is a 24 h slip (k = 27); a 709 h slip leaves the data; 709 h after the headline 2026-01-01T03 is 2026-01-30T16."""
    safe = np.zeros(40, bool)
    safe[[3, 4, 5, 6, 30]] = True
    starts = np.array([str(np.datetime64("2026-01-01T00") + np.timedelta64(h, "h")) for h in range(40)])
    assert consecutive_safe(safe, 3) == 4 and consecutive_safe(safe, 30) == 1 and consecutive_safe(safe, 7) == 0
    rows = delay_ladder(safe, 3, starts)
    assert [r["slip_h"] for r in rows] == [1, 6, 24, 709]
    assert rows[0] == {"slip_h": 1, "start_utc": "2026-01-01T04", "safe": True, "next_safe_utc": "2026-01-01T04"}
    assert not rows[1]["safe"] and rows[1]["next_safe_utc"] == "2026-01-02T06"
    assert not rows[2]["safe"] and rows[2]["next_safe_utc"] == "2026-01-02T06"
    assert rows[3]["safe"] is False and rows[3]["next_safe_utc"] is None
    assert rows[3]["label"] == "one lunation (29.53 days)" and rows[3]["start_utc"] == "2026-01-30T16"
    lookup = {t[:13]: bool(v) for t, v in zip(starts, safe)}         # every non-null next_safe_utc is a safe hour
    assert all(lookup[r["next_safe_utc"]] for r in rows if r["next_safe_utc"] is not None)


def test_miss_table_agrees_with_safe_100m_and_a_steep_point_fails_on_slope_first(tmp_path):
    """Spec commit 1: two points, the second behind a ridge (skyline 5 deg toward theta 0, the Sun at az 10 and
    el 1 never clears it), so it is dark at touchdown and no hour is safe within 100 m."""
    hours = 24
    sky = {"sun_az": np.full((1, 48), 10.0), "sun_el": np.ones((1, 48)), "earth_az": np.full((1, 48), 90.0),
           "earth_el": np.full((1, 48), 2.0), "sun_radius_deg": np.full(48, 0.27),
           "earth_radius_deg": np.full(48, 0.95)}
    H_points = np.zeros((2, 1, 4))
    H_points[1, 0, 0] = 5.0
    np.save(tmp_path / "horizon.npy", H_points)
    np.save(tmp_path / "complete.npy", np.ones((2, 1, 4), bool))
    parent_safe = date_metrics(*visibility(np.zeros((1, 1, 4)), sky, 0.0), hours, Battery(), 0.5)["safe"]
    assert parent_safe[0, 0].all()
    safe_100m, _, _, det = neighbour_safe(tmp_path, sky, hours, Battery(), 0.0, 0.5, np.array([0, 0]), parent_safe,
                                          np.array([False, False]), details=True)
    nb = {"id": np.array(["s_0", "s_1"]), "x": np.array(["0", "100"]), "y": np.array(["0", "0"]),
          "slope": np.array(["3.0", "4.0"])}
    rows = miss_table(np.array([0, 1]), nb, 0.0, 0.0, det["s"], det["e"], det["met"], 0, 0, hours, 0.5)
    assert [r["safe"] for r in rows] == [True, False] and rows[0]["fails"] is None
    assert rows[1] == {"point": "s_1", "dx_m": 100.0, "dy_m": 0.0, "safe": False, "fails": "sun at touchdown"}
    assert all(r["safe"] for r in rows) == bool(safe_100m[0, 0, 0])
    nb["slope"] = np.array(["3.0", "12.0"])                       # steep and dark: slope is reported first
    rows = miss_table(np.array([0, 1]), nb, 0.0, 0.0, det["s"], det["e"], det["met"], 0, 0, hours, 0.5)
    assert rows[1]["fails"] == "slope"
    words = risk_words(4, delay_ladder(parent_safe[0, 0], 0, np.array(
        [str(np.datetime64("2026-01-01T00") + np.timedelta64(h, "h")) for h in range(25)])), rows, 0.0,
        {"s_0": 3.0, "s_1": 12.0}, "within 100 m")
    assert words[0].startswith("Land up to 3 h late and it is still safe within 100 m")
    # a site with no date safe within 100 m counts its delays on the exact point, and says so
    on_point = risk_words(1, [], None, 0.0, None, "exact point")
    assert on_point[0].startswith("Only the headline hour itself is safe on the exact point (no date here is safe")
    assert words[1] == ("Missed by up to 100 m: 1 of 2 points safe; at the point 100 m toward bearing 90 deg, "
                        "its ground slopes 12.0 deg over 100 m.")
