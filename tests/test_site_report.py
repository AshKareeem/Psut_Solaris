from pathlib import Path

import numpy as np
import pytest

from scripts.battery import Battery
from scripts.site_report import bearing, longest_span, site_report, weak_battery_block

DATA = Path(__file__).resolve().parents[1] / "data"
SITE = {"id": "t", "lat": -89.5, "lon": 0.0, "x_m": 0.0, "y_m": 15161.0}


def track(sun_el, earth_el, sun_az=10.0, earth_az=90.0):
    n = len(sun_el)
    times = np.array([str(np.datetime64("2027-01-01T00:00:00") + np.timedelta64(h, "h")) for h in range(n)])
    return {"time_utc": times, "sun_az": np.full(n, sun_az), "sun_el": np.asarray(sun_el, float),
            "earth_az": np.full(n, earth_az), "earth_el": np.asarray(earth_el, float),
            "sun_radius_deg": np.full(n, 0.27), "earth_radius_deg": np.full(n, 0.95)}


def test_bearing_and_spans():
    assert bearing(90.0, 0.0) == 0.0 and bearing(0.0, 0.0) == 90.0      # at lon 0: map up is north, map right east
    assert longest_span(np.array([False, True, True, False, True])) == (1, 2)
    assert longest_span(np.zeros(3, bool)) == (None, 0)


def test_report_explains_a_dark_spell_with_the_blocking_terrain():
    H, D = np.zeros(360), np.full(360, 5000.0)
    H[5:16], D[5:16] = 3.0, 8200.0                             # a ridge 8.2 km away toward theta 5-15 deg
    sun = [1.0] * 6 + [1.0] * 12 + [1.0] * 6                  # the Sun at 1 deg: lit unless behind the ridge
    t = track(sun, [2.0] * 24)
    t["sun_az"][6:18] = 10.0                                  # behind the ridge for 12 hours
    t["sun_az"][:6] = t["sun_az"][18:] = 100.0
    rep = site_report(SITE, H, D, np.ones(360, bool), t, 2.0, Battery(), 0.0)
    assert rep["summary"]["longest_dark_h"] == 12 and rep["summary"]["battery_used_Wh"] == 600.0   # > the 560 Wh it can use
    assert rep["summary"]["touchdown_sun"] and not rep["summary"]["survives"]   # 12 dark hours > 11.2 h bridge
    assert "8.2 km" in rep["why"][0] and "bearing 80 deg" in rep["why"][0]
    assert rep["events"]["sunlit"][0]["start"] is None and len(rep["events"]["sunlit"]) == 2
    assert len(rep["hourly"]["sun_fraction"]) == 24 and len(rep["skyline"]["horizon_deg"]) == 360
    assert "AI assistance" in rep["provenance"]                # the rules: generation acknowledged in metadata


def test_a_good_site_says_why_and_a_close_touchdown_is_marginal():
    """Council R10: why[] was empty for good sites; H9: site 210's Earth cleared the skyline by only 0.11 deg."""
    H, D = np.zeros(360), np.full(360, 3000.0)
    H[85:96] = 1.0                                             # a hill 3 km away toward Earth
    sun = [1.0] * 12 + [0.6] * 12                              # never below the flat skyline; lowest at hour 12
    rep = site_report(SITE, H, D, np.ones(360, bool), track(sun, [0.3] * 24), 2.0, Battery(), 0.0)
    assert rep["summary"]["marginal"] and rep["summary"]["longest_dark_h"] == 0
    marginal, sun_up, earth_up = rep["why"]
    assert marginal.startswith("Marginal touchdown: the top of Earth's disc") and "0.25 deg above" in marginal
    assert "3.0 km away" in marginal                           # the hill toward theta 90
    assert sun_up.startswith("The Sun stays up all mission") and "2027-01-01T12" in sun_up
    assert earth_up.startswith("Earth stays in view all mission")
    rep = site_report(SITE, H, D, np.ones(360, bool), track([1.0] * 24, [2.0] * 24), 2.0, Battery(), 0.0)
    assert not rep["summary"]["marginal"]


@pytest.mark.skipif(not (DATA / "ldem_75s_240m.lbl").exists() or not (DATA / "kernels" / "de421.bsp").exists(),
                    reason="LOLA 240 m map or SPICE kernels missing")
def test_analyze_any_coordinates_end_to_end():
    from scripts.analyze import analyze
    rep = analyze(-89.5, 200.0, 10.0, "2027-03-01T06", 2, DATA / "ldem_75s_240m.lbl")
    assert rep["site"]["lon"] == -160.0 and rep["mission"] == {"start_utc": "2027-03-01T06", "hours": 48}
    assert len(rep["hourly"]["time_utc"]) == 48 and all(rep["skyline"]["complete"])


def flat(n=360):
    return np.zeros(n), np.full(n, 5000.0), np.ones(n, bool)


def test_contact_plan_windows_are_dte_entries_and_missing_names_the_gap():
    """Spec commit 2, tests 1-2. Earth up 6 h, down 6, up 12: two DTE windows; touchdown (hour 0) is in the first,
    mid-mission (hour 12) and end (hour 23) in the second; nothing missing."""
    H, D, ok = flat()
    rep = site_report(SITE, H, D, ok, track([1.0] * 24, [2.0] * 6 + [-2.0] * 6 + [2.0] * 12), 2.0, Battery(), 0.0)
    cp = rep["contact_plan"]
    assert cp["missing"] == [] and cp["longest_blackout_h"] == rep["summary"]["longest_earth_blackout_h"]
    assert len(cp["windows"]) == 2
    for w in cp["windows"]:
        assert {"start": w["start"], "end": w["end"]} in rep["events"]["dte"]
    assert cp["windows"][0]["covers"] == ["touchdown"] and cp["windows"][1]["covers"] == ["mid-mission", "end"]
    assert cp["first_contact_utc"] == "2027-01-01T00:00:00"   # the sky file stamps carry seconds
    # Earth sets for good before mid-mission: the plan cannot be confirmed mid-mission or at the end
    rep = site_report(SITE, H, D, ok, track([1.0] * 24, [2.0] * 12 + [-2.0] * 12), 2.0, Battery(), 0.0)
    assert rep["contact_plan"]["missing"] == ["mid-mission", "end"]
    # Earth hidden at touchdown: first contact is the first window's start, to the minute
    rep = site_report(SITE, H, D, ok, track([1.0] * 24, [-2.0] * 12 + [2.0] * 12), 2.0, Battery(), 0.0)
    cp = rep["contact_plan"]
    assert cp["missing"] == ["touchdown"] and cp["first_contact_utc"] == rep["events"]["dte"][0]["start"]


def test_dark_verdict_agrees_with_the_summary():
    """Spec commit 2, test 3: the 12-hour ridge spell from the first test kills the battery (bridge 11.2 h), so
    exactly one run, lasts False, and its length is the summary's longest_dark_h."""
    H, D = np.zeros(360), np.full(360, 5000.0)
    H[5:16], D[5:16] = 3.0, 8200.0
    t = track([1.0] * 24, [2.0] * 24)
    t["sun_az"][6:18] = 10.0
    t["sun_az"][:6] = t["sun_az"][18:] = 100.0
    rep = site_report(SITE, H, D, np.ones(360, bool), t, 2.0, Battery(), 0.0)
    runs = rep["dark_verdict"]
    assert len(runs) == 1 and runs[0]["hours"] == rep["summary"]["longest_dark_h"] == 12
    assert runs[0]["start"] == "2027-01-01T06" and runs[0]["end"] == "2027-01-01T18"
    assert runs[0]["battery_start_Wh"] == 700.0 and runs[0]["battery_lowest_Wh"] == rep["summary"]["battery_lowest_Wh"]
    assert any(not r["lasts"] for r in runs) == (not rep["summary"]["survives"])
    rep = site_report(SITE, *flat(), track([1.0] * 24, [2.0] * 24), 2.0, Battery(), 0.0)
    assert rep["dark_verdict"] == [] and rep["summary"]["survives"]          # the Sun never sets
    assert any(not r["lasts"] for r in rep["dark_verdict"]) == (not rep["summary"]["survives"])


def test_weak_battery_at_factor_1_reproduces_the_summary():
    """Spec commit 2, test 4. 11 dark hours then Sun: the full battery survives at 150 Wh (test_battery_matches...),
    at half capacity (350 Wh, reserve 70 Wh) the 50 W load passes 70 Wh during hour 5: 350 - 50 x 6 = 50 Wh."""
    rep = site_report(SITE, *flat(), track([-1.0] * 11 + [1.0] * 13, [2.0] * 24), 2.0, Battery(), 0.0)
    s = np.array(rep["hourly"]["sun_fraction"])
    full = weak_battery_block(s, Battery(), 1.0)
    assert full["survives"] == rep["summary"]["survives"] is True
    assert full["dies_at_hour"] == rep["summary"]["dies_at_hour"] is None
    wb = rep["weak_battery"]
    assert wb["capacity_factor"] == 0.5 and wb["e_max_Wh"] == 350.0 and wb["e_min_Wh"] == 70.0
    assert wb["survives"] is False and wb["dies_at_hour"] == 5 and "assumption" in wb["label"]
    assert any("at best (sun-tracking panels)" in w for w in rep["words"])
