from pathlib import Path

import numpy as np
import pytest

from scripts.validate_horizons import _horizons_hour, horizons_url, julian_date, ours, parse_table

KERNELS = Path(__file__).resolve().parents[1] / "data" / "kernels"
RIM_LAT, RIM_LON = -89.778601, -155.72556

# Answers JPL Horizons gave on Nov 13, 2026 for the rim site (Earth), recorded so the test runs offline
RESULT = """*******
$$SOE
 2024-Feb-22 23:00:00.000,*,i, 158.709224,     5.363498,
 2026-Mar-01 00:00:00.000,*,i, 159.512019,     2.902970,
 2026-Mar-01 18:00:00.000, ,i, 159.952028,     1.783595,
$$EOE
*******"""
TIMES = ["2024-02-22T23", "2026-03-01T00", "2026-03-01T18"]


def test_julian_date_and_horizons_time_stamps():
    assert julian_date("2000-01-01T12") == 2451545.0                  # J2000
    assert _horizons_hour(" 2024-Feb-22 23:00:00.000") == "2024-02-22T23"
    url = horizons_url("earth", RIM_LAT, RIM_LON, TIMES)
    assert "coord%40301" in url and "204.274440" in url and "AIRLESS" in url   # east longitude 0-360


def test_parse_reads_the_table_and_fails_on_other_times():
    az, el = parse_table(RESULT, TIMES)
    assert az[0] == 158.709224 and el[2] == 1.783595
    with pytest.raises(ValueError, match="asked for"):
        parse_table(RESULT, ["2024-02-22T23", "2026-03-01T00", "2026-03-01T19"])
    with pytest.raises(ValueError, match="no table"):
        parse_table("API error: bad site", TIMES)


@pytest.mark.skipif(not (KERNELS / "de421.bsp").exists(), reason="SPICE kernels missing")
def test_make_sky_matches_recorded_horizons_answers():
    from scripts.make_sky import load_kernels
    load_kernels(str(KERNELS))
    az_h, el_h = parse_table(RESULT, TIMES)
    az, el = ours(np.array([RIM_LAT]), np.array([RIM_LON]), TIMES)["earth"]
    assert np.abs((az[0] - az_h + 180) % 360 - 180).max() < 1e-4
    assert np.abs(el[0] - el_h).max() < 1e-4
