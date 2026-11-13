from pathlib import Path

import numpy as np
import pytest

from scripts.battery import Battery
from scripts.site_report import bearing, longest_span, site_report

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
    assert rep["summary"]["longest_dark_h"] == 12 and rep["summary"]["battery_needed_Wh"] == 600.0   # > the 560 Wh it can use
    assert rep["summary"]["touchdown_sun"] and not rep["summary"]["survives"]   # 12 dark hours > 11.2 h bridge
    assert "8.2 km" in rep["why"][0] and "bearing 80 deg" in rep["why"][0]
    assert rep["events"]["sunlit"][0]["start"] is None and len(rep["events"]["sunlit"]) == 2
    assert len(rep["hourly"]["sun_fraction"]) == 24 and len(rep["skyline"]["horizon_deg"]) == 360


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
