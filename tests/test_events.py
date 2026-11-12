import numpy as np

from scripts.events import intervals, overlap, site_events, until_end


def test_crossings_are_interpolated_between_hours():
    c = np.array([-1.0, 1.0, 3.0, 1.0, -3.0, -1.0])         # up between hours 0-1, down between 3-4
    assert intervals(c) == [(0.5, 3.25)]


def test_spans_open_at_the_series_edges():
    assert intervals(np.array([1.0, -1.0, -1.0, 1.0])) == [(None, 0.5), (2.5, None)]
    assert intervals(np.array([1.0, 2.0])) == [(None, None)] and intervals(np.array([-1.0, -2.0])) == []


def test_overlap_and_time_left():
    sun, earth = [(None, 5.0), (10.0, 20.0)], [(3.0, 12.0)]
    assert overlap(sun, earth) == [(3.0, 5.0), (10.0, 12.0)]
    assert until_end(sun, 0.0) == 5.0 and until_end(sun, 7.0) == 0.0 and until_end([(None, None)], 3.0) is None


def test_synthetic_month_of_sunrise_and_sunset():
    """A Sun circling a flat skyline once a day at 1 deg amplitude: up for exactly half of every day."""
    t = np.arange(72)
    sun = np.sin(2 * np.pi * (t - 6) / 24)                  # crosses 0 at hours 6, 18, 30, ...
    ev = site_events(sun, np.ones(72), np.datetime64("2027-01-01T00:00"))
    assert [w["start"] for w in ev["sunlit"]] == ["2027-01-01T06:00", "2027-01-02T06:00", "2027-01-03T06:00"]
    assert [w["end"] for w in ev["sunlit"]] == ["2027-01-01T18:00", "2027-01-02T18:00", "2027-01-03T18:00"]
    assert ev["dte"] == [{"start": None, "end": None}] and ev["both"] == ev["sunlit"]
    assert ev["hours_to_sunset"] == 0.0 and ev["hours_to_earthset"] is None
