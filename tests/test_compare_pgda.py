import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("pyproj")
from rasterio.transform import from_origin  # noqa: E402

from horizon.dem import latlon_to_xy, xy_to_latlon  # noqa: E402
from scripts.compare_pgda import read_window  # noqa: E402

MOON_STEREO = "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
N, PIXEL = 201, 60.0
HALF = N * PIXEL / 2


def fake_map(tmp_path):
    """A fake NASA-style map: value = 100*col + row (int16 * 0.001), pole at the centre."""
    rows, cols = np.mgrid[0:N, 0:N]
    path = tmp_path / "fake.tif"
    with rasterio.open(path, "w", driver="GTiff", width=N, height=N, count=1, dtype="int16",
                       crs=MOON_STEREO, transform=from_origin(-HALF, HALF, PIXEL, PIXEL), nodata=-32768) as dst:
        dst.write((cols * 100 + rows).astype(np.int16), 1)
        dst.scales, dst.offsets = (0.001,), (0.0,)
    return path


def test_reads_the_right_pixel_with_scaling_and_its_centre(tmp_path):
    lat, lon = -89.9, 200.0
    block, lat_c, lon_c, info = read_window(fake_map(tmp_path), lat, lon, 3)
    x, y = info["site_xy"]
    ox, oy = latlon_to_xy(lat, lon)
    assert np.hypot(x - ox, y - oy) < 1e-3          # PROJ's south stereographic == ours
    col, row = int((x + HALF) // PIXEL), int((HALF - y) // PIXEL)
    assert block[1, 1] == pytest.approx((col * 100 + row) * 0.001)
    cx, cy = latlon_to_xy(lat_c[1, 1], lon_c[1, 1])
    assert np.hypot(cx - (-HALF + (col + 0.5) * PIXEL), cy - (HALF - (row + 0.5) * PIXEL)) < 1e-3


def test_site_on_a_pixel_corner_gets_the_four_pixels_touching_it(tmp_path):
    lat, lon = xy_to_latlon(-HALF + 120 * PIXEL, HALF - 80 * PIXEL)  # the corner between cols 119-120, rows 79-80
    block, _, _, info = read_window(fake_map(tmp_path), lat, lon, 2)
    assert np.allclose(block, [[11979 * 0.001, 12079 * 0.001], [11980 * 0.001, 12080 * 0.001]])
    assert np.allclose(info["site_pixel"], (120, 80))
