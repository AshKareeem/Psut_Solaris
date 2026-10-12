import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("pyproj")
from rasterio.transform import from_origin  # noqa: E402

from horizon.dem import latlon_to_xy  # noqa: E402
from scripts.compare_pgda import read_site  # noqa: E402

MOON_STEREO = "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"


def test_reads_the_right_pixel_with_scaling(tmp_path):
    """A fake NASA-style map: value = 1000*col + row (int16 * 0.001), pole at the centre."""
    n, pixel = 201, 60.0
    rows, cols = np.mgrid[0:n, 0:n]
    dn = (cols * 100 + rows).astype(np.int16)
    path = tmp_path / "fake.tif"
    half = n * pixel / 2
    with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=1, dtype="int16",
                       crs=MOON_STEREO, transform=from_origin(-half, half, pixel, pixel), nodata=-32768) as dst:
        dst.write(dn, 1)
        dst.scales, dst.offsets = (0.001,), (0.0,)

    lat, lon = -89.9, 200.0
    block, (x, y), info = read_site(path, lat, lon, radius=1)
    ox, oy = latlon_to_xy(lat, lon)
    assert np.hypot(x - ox, y - oy) < 1e-3          # PROJ's south stereographic == ours
    col = int((x + half) // pixel)
    row = int((half - y) // pixel)
    assert block[1, 1] == pytest.approx((col * 100 + row) * 0.001)
