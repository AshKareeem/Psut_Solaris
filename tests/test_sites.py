import numpy as np
import pytest

from horizon.dem import PolarDEM, latlon_to_xy
from horizon.sites import grid_around, read_sites, slope_deg, write_sites
from horizon.synthetic import cone, distance_grid


def cone_dem():
    """A 500 m cone (slope atan(0.25) = 14.04 deg) on a 401 x 401 grid of 20 m pixels, peak at row 150, col 250."""
    z = cone(distance_grid(401, 20.0, 150, 250), peak=500.0, base_radius=2000.0)
    return PolarDEM(height=z.astype(np.float32), pixel=20.0, pole_row=200.0, pole_col=200.0)


def test_demo_grid_round_trip(tmp_path):
    dem = cone_dem()
    rows, cols = grid_around(dem, *dem.rowcol_to_latlon(150, 250), n=3, step=5)
    assert (rows[4], cols[4]) == (150, 250)  # the centre site is the requested pixel
    write_sites(tmp_path / "sites.csv", dem, rows, cols)
    ids, x, y = read_sites(tmp_path / "sites.csv")
    r, c = dem.xy_to_rowcol(x, y)
    assert ids == [str(i) for i in range(9)]
    assert np.allclose(r, rows, atol=1e-3) and np.allclose(c, cols, atol=1e-3)


def test_grid_off_the_map_fails_fast():
    dem = cone_dem()
    with pytest.raises(ValueError, match="runs off the map"):
        grid_around(dem, *dem.rowcol_to_latlon(5, 200), n=3, step=5)  # would wrap to the bottom rows


def test_slope_on_the_cone_flank():
    assert slope_deg(cone_dem(), np.array([150]), np.array([255]))[0] == pytest.approx(np.degrees(np.arctan(0.25)))


def test_missing_column_fails_fast(tmp_path):
    (tmp_path / "s.csv").write_text("id,x,y,lat,lon,height\n0,0,0,-90,0,0\n")
    with pytest.raises(ValueError, match=r"missing columns \['slope'\]"):
        read_sites(tmp_path / "s.csv")


def test_xy_that_disagree_with_latlon_fail_fast(tmp_path):
    """Catches swapped axes or another projection in Step 0's file."""
    x, y = latlon_to_xy(-89.5, 30.0)
    (tmp_path / "s.csv").write_text(f"id,x,y,lat,lon,height,slope\n0,{y},{x},-89.5,30.0,0,0\n")  # x and y swapped
    with pytest.raises(ValueError, match="disagree"):
        read_sites(tmp_path / "s.csv")


def test_duplicate_ids_fail_fast(tmp_path):
    x, y = latlon_to_xy(-89.5, 30.0)
    (tmp_path / "s.csv").write_text(f"id,x,y,lat,lon,height,slope\n7,{x},{y},-89.5,30,0,0\n7,{x},{y},-89.5,30,0,0\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_sites(tmp_path / "s.csv")
