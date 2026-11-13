import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from horizon.dem import POLAR_PROJ4, read_polar_geotiff
from scripts.moontrek import EXTENT, PIXEL, despike, export_url, window


def _tif(path, z, x_min, y_max, px, crs=POLAR_PROJ4):
    with rasterio.open(path, "w", driver="GTiff", width=z.shape[1], height=z.shape[0], count=1, dtype="float32",
                       crs=crs, transform=from_origin(x_min, y_max, px, px)) as d:
        d.write(z.astype(np.float32), 1)


def test_geotiff_window_maps_pixel_centres_to_map_metres(tmp_path):
    z = np.arange(12, dtype=np.float32).reshape(3, 4)
    _tif(tmp_path / "w.tif", z, x_min=-1000.0, y_max=500.0, px=5.0)
    dem = read_polar_geotiff(tmp_path / "w.tif")
    assert dem.pixel == 5.0
    assert dem.rowcol_to_xy(0, 0) == (-997.5, 497.5)                  # centre of the top-left pixel
    r, c = dem.xy_to_rowcol(-987.5, 487.5)
    assert (r, c) == (2.0, 2.0) and dem.height[2, 2] == 10.0


def test_geotiff_on_another_map_fails(tmp_path):
    _tif(tmp_path / "w.tif", np.zeros((2, 2)), 0.0, 10.0, 5.0, crs="+proj=stere +lat_0=-90 +lon_0=0 +R=1738000")
    with pytest.raises(ValueError, match="not the south polar stereographic map"):
        read_polar_geotiff(tmp_path / "w.tif")


def test_despike_removes_a_needle_and_keeps_a_steep_slope():
    yy, xx = np.mgrid[0:40, 0:40]
    slope = (xx * 5.0 * np.tan(np.radians(30))).astype(np.float32)   # a 30 deg slope: real terrain, kept
    z = slope.copy()
    z[20, 20] += 210.0                                               # IM-site-190-like needle
    clean, n = despike(z)
    assert n == 1 and abs(clean[20, 20] - slope[20, 20]) < 1e-3
    assert np.array_equal(np.delete(clean.ravel(), 20 * 40 + 20), np.delete(slope.ravel(), 20 * 40 + 20))


def test_window_is_on_the_5_m_grid_and_inside_the_map():
    b = window(-2759.98, -5639.96, 1000.0)
    assert all(v % PIXEL == 0 for v in b) and b[0] <= -3759.98 and b[2] >= -1759.98
    assert "size=400%2C400" in export_url(window(-2760.0, -5640.0, 1000.0))
    with pytest.raises(ValueError, match="leaves the 5 m map"):
        window(EXTENT - 100.0, 0.0, 1000.0)
    with pytest.raises(ValueError, match="wider than"):
        window(0.0, 0.0, 12000.0)


def test_nac_tile_grid_puts_the_pole_on_the_tile_corner_seen_in_the_service():
    from scripts.moontrek import NAC_ORIGIN, NAC_PIXEL0, tile_span
    px, cols, rows = tile_span(0.0, 0.0, 1.0, 3)            # probing the service: data in tiles 3-4 at level 3
    assert cols == (3, 4) and rows == (3, 4)
    assert abs(px - NAC_PIXEL0 / 8) < 1e-9 and abs(256 * NAC_PIXEL0 - 2 * NAC_ORIGIN) < 1.0   # level 0: one tile wide
