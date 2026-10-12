import numpy as np
import pytest

from horizon.dem import read_polar_dem
from horizon.reference import R, horizon_profile
from horizon.synthetic import cone, distance_grid

LABEL = """PDS_VERSION_ID = PDS3
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = 10
^IMAGE = "FAKE.IMG"
OBJECT = IMAGE
  LINES = 5
  LINE_SAMPLES = 5
  SAMPLE_TYPE = LSB_INTEGER
  SAMPLE_BITS = 16
  UNIT = METER
  SCALING_FACTOR = 0.5
  OFFSET = {offset}
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  MAP_PROJECTION_TYPE = "POLAR STEREOGRAPHIC"
  CENTER_LATITUDE = -90.0 <DEG>
  CENTER_LONGITUDE = 0.0 <DEG>
  MAP_SCALE = 240.0 <METERS/PIXEL>
  LINE_PROJECTION_OFFSET = 2.0 <PIXEL>
  SAMPLE_PROJECTION_OFFSET = 2.0 <PIXEL>
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""


def write_fake(tmp_path, offset="1737400."):
    (tmp_path / "FAKE.LBL").write_text(LABEL.format(offset=offset))
    np.arange(25, dtype="<i2").tofile(tmp_path / "fake.img")  # lower case on disk on purpose
    return tmp_path / "FAKE.LBL"


def test_reads_heights_scale_and_pole(tmp_path):
    dem = read_polar_dem(write_fake(tmp_path))
    assert dem.height.shape == (5, 5) and dem.height[1, 2] == 3.5  # DN 7 * 0.5 m
    assert dem.pixel == 240.0 and dem.center == 2.0
    lat, _ = dem.rowcol_to_latlon(2, 2)
    assert lat == -90.0


def test_latlon_round_trip(tmp_path):
    dem = read_polar_dem(write_fake(tmp_path))
    row, col = dem.latlon_to_rowcol(-89.5, 30.0)
    lat, lon = dem.rowcol_to_latlon(row, col)
    assert abs(lat + 89.5) < 1e-9 and abs(lon - 30.0) < 1e-9


def test_wrong_reference_sphere_fails_fast(tmp_path):
    with pytest.raises(ValueError, match="1737.4 km"):
        read_polar_dem(write_fake(tmp_path, offset="1738000."))


def test_longitude_0_is_map_up_and_90E_is_map_right(tmp_path):
    """Pins the direction convention shared with the Sun/Earth (SPICE) code."""
    dem = read_polar_dem(write_fake(tmp_path))
    dem.pixel, dem.center = 20.0, 1000.0
    for lon, expected_theta in ((0.0, 90.0), (90.0, 0.0)):
        row, col = dem.latlon_to_rowcol(-90 + np.degrees(10_000 / R), lon)  # 10 km from the pole
        terrain = cone(distance_grid(2001, 20.0, row, col), peak=1000.0, base_radius=3000.0)
        H, _, _ = horizon_profile(terrain, 20.0, 1000, 1000, mast=0.0, d_max=15_000, n_az=360)
        assert np.argmax(H) == expected_theta
