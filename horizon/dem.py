"""Read LOLA south-polar DEMs (PDS3 .LBL + .IMG) and convert between lat/lon and grid positions.

Map convention (PDS polar stereographic, south pole):
  - the pole is at the centre of a square grid (pixel (n-1)/2); a crop keeps the pole's position in its own indices
  - map x points right (toward longitude 90E), map y points up (toward longitude 0)
  - row 0 is the top of the image, so +y means a smaller row index
"""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from horizon.reference import R

_DTYPES = {("LSB_INTEGER", 16): "<i2", ("MSB_INTEGER", 16): ">i2", ("PC_REAL", 32): "<f4"}


@dataclass
class PolarDEM:
    height: np.ndarray  # float32, metres above the 1737.4 km sphere, indexed [row, col]
    pixel: float        # metres per pixel
    pole_row: float     # row and column index of the pole; outside the grid for a crop away from the pole
    pole_col: float

    def latlon_to_rowcol(self, lat_deg, lon_deg):
        return self.xy_to_rowcol(*latlon_to_xy(lat_deg, lon_deg))

    def xy_to_rowcol(self, x, y):
        return self.pole_row - np.asarray(y) / self.pixel, self.pole_col + np.asarray(x) / self.pixel

    def rowcol_to_xy(self, row, col):
        return (np.asarray(col) - self.pole_col) * self.pixel, (self.pole_row - np.asarray(row)) * self.pixel

    def rowcol_to_latlon(self, row, col):
        return xy_to_latlon(*self.rowcol_to_xy(row, col))


def latlon_to_xy(lat_deg, lon_deg):
    """South polar stereographic on the 1737.4 km sphere, true scale at the pole. Metres."""
    rho = 2 * R * np.tan(np.radians(90 + np.asarray(lat_deg)) / 2)
    lon = np.radians(lon_deg)
    return rho * np.sin(lon), rho * np.cos(lon)


def xy_to_latlon(x, y):
    rho = np.hypot(x, y)
    return -90 + np.degrees(2 * np.arctan(rho / (2 * R))), np.degrees(np.arctan2(x, y))


def read_polar_dem(label_path, bounds=None):
    """Load a south-polar LOLA DEM from its PDS3 label. Fails fast on anything unexpected.

    bounds = (x_min, x_max, y_min, y_max) in map metres loads only the pixels needed there. The image is
    memory-mapped, so a crop of a 1.8 GB map reads just the crop.
    """
    label_path = Path(label_path)
    lbl = _read_label(label_path)

    if "POLAR STEREOGRAPHIC" not in lbl["MAP_PROJECTION_TYPE"].upper():
        raise ValueError(f"not a polar stereographic map: {lbl['MAP_PROJECTION_TYPE']}")
    if _number(lbl["CENTER_LATITUDE"]) != -90:
        raise ValueError("expected a south-pole map (CENTER_LATITUDE = -90)")
    if _number(lbl["CENTER_LONGITUDE"]) != 0:
        raise ValueError("expected CENTER_LONGITUDE = 0")

    n = int(_number(lbl["LINES"]))
    if int(_number(lbl["LINE_SAMPLES"])) != n:
        raise ValueError("expected a square grid centred on the pole")
    center = (n - 1) / 2
    for key in ("LINE_PROJECTION_OFFSET", "SAMPLE_PROJECTION_OFFSET"):
        if key in lbl and min(abs(_number(lbl[key]) - c) for c in (center, n / 2)) > 1:
            raise ValueError(f"{key} = {lbl[key]} does not put the pole at the grid centre")

    dtype = _DTYPES.get((lbl["SAMPLE_TYPE"].strip('"'), int(_number(lbl["SAMPLE_BITS"]))))
    if dtype is None:
        raise ValueError(f"unsupported sample type {lbl['SAMPLE_TYPE']} / {lbl['SAMPLE_BITS']} bits")
    if "UNIT" in lbl and lbl["UNIT"].strip('"').upper() not in ("METER", "METERS"):
        raise ValueError(f"expected heights in metres, label says UNIT = {lbl['UNIT']}")
    if abs(_metres(lbl["OFFSET"]) - R) > 1:
        raise ValueError(f"OFFSET = {lbl['OFFSET']} is not the 1737.4 km reference sphere")

    img_path, byte_offset = _image_location(label_path, lbl)
    if img_path.stat().st_size < byte_offset + n * n * np.dtype(dtype).itemsize:
        raise ValueError(f"{img_path.name} is too short for {n} x {n} samples")
    pixel = _metres(lbl["MAP_SCALE"])
    r0, r1, c0, c1 = (0, n, 0, n) if bounds is None else _window(bounds, center, pixel, n)
    dn = np.memmap(img_path, dtype=dtype, mode="r", offset=byte_offset, shape=(n, n))[r0:r1, c0:c1]
    height = dn.astype(np.float32) * np.float32(_number(lbl["SCALING_FACTOR"]))
    if "MISSING_CONSTANT" in lbl:
        height[dn == _number(lbl["MISSING_CONSTANT"])] = np.nan

    return PolarDEM(height=height, pixel=pixel, pole_row=center - r0, pole_col=center - c0)


POLAR_PROJ4 = "+proj=stere +lat_0=-90 +lon_0=0 +k=1 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"


def read_polar_geotiff(path):
    """Load a south-polar height GeoTIFF (e.g. a NASA Moon Trek window, scripts/moontrek.py) as a PolarDEM.

    Fails fast unless the file uses this module's map (south polar stereographic on the 1737.4 km sphere, checked by
    projecting points) with square, unrotated pixels. Heights must be metres above the 1737.4 km sphere, as LOLA's
    are; the file's own metadata can't say so, so the caller vouches for it (Moon Trek: "Map values are referred
    to a radius of 1737400 m").
    """
    import rasterio
    from pyproj import CRS, Transformer

    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError(f"{path}: no map projection")
        to_ours = Transformer.from_crs(src.crs, CRS.from_proj4(POLAR_PROJ4), always_xy=True)
        for x, y in ((0.0, 0.0), (50e3, -30e3), (-120e3, 80e3)):
            xo, yo = to_ours.transform(x, y)
            if abs(xo - x) > 1e-3 or abs(yo - y) > 1e-3:
                raise ValueError(f"{path}: not the south polar stereographic map on the 1737.4 km sphere")
        t = src.transform
        if t.b != 0 or t.d != 0 or abs(t.a + t.e) > 1e-9 or t.a <= 0:
            raise ValueError(f"{path}: pixels must be square, north-up and unrotated (transform {tuple(t)[:6]})")
        height = src.read(1).astype(np.float32)
        if src.nodata is not None:
            height[height == src.nodata] = np.nan
    pixel = float(t.a)
    return PolarDEM(height=height, pixel=pixel, pole_row=t.f / pixel - 0.5, pole_col=-t.c / pixel - 0.5)


def map_half_width(label_path):
    """Distance (m) from the pole to the centre of the map's edge pixels, read from the label alone."""
    lbl = _read_label(Path(label_path))
    return (_number(lbl["LINES"]) - 1) / 2 * _metres(lbl["MAP_SCALE"])


def _window(bounds, center, pixel, n):
    """Rows [r0, r1) and columns [c0, c1) holding every pixel bilinear interpolation needs inside bounds."""
    x_min, x_max, y_min, y_max = bounds
    r0, r1 = int(np.floor(center - y_max / pixel)), int(np.ceil(center - y_min / pixel)) + 2
    c0, c1 = int(np.floor(center + x_min / pixel)), int(np.ceil(center + x_max / pixel)) + 2
    r0, r1, c0, c1 = max(r0, 0), min(r1, n), max(c0, 0), min(c1, n)
    if r0 >= r1 or c0 >= c1:
        raise ValueError(f"bounds {bounds} lie outside the map")
    return r0, r1, c0, c1


def _read_label(path):
    """First value of every KEY = value line (enough for the keys we use)."""
    keys = {}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"\s*(\^?[A-Z_]+)\s*=\s*(.+?)\s*$", line)
        if m and m.group(1) not in keys:
            keys[m.group(1)] = m.group(2)
    return keys


def _number(value):
    return float(re.match(r"\s*\(?\s*([-+0-9.Ee]+)", value).group(1))


def _metres(value):
    """Number with an optional <unit>; kilometres are converted to metres."""
    unit = re.search(r"<([^>]+)>", value)
    factor = 1000.0 if unit and unit.group(1).upper().startswith(("KM", "KILOMETER")) else 1.0
    return _number(value) * factor


def _image_location(label_path, lbl):
    """Resolve ^IMAGE = "FILE.IMG" or ("FILE.IMG", start_record) to (path, byte offset)."""
    pointer = lbl["^IMAGE"]
    name = re.search(r'"([^"]+)"', pointer)
    if name is None:
        raise ValueError(f"only detached labels are supported, got ^IMAGE = {pointer}")
    record = re.search(r",\s*(\d+)", pointer)
    offset = (int(record.group(1)) - 1) * int(_number(lbl["RECORD_BYTES"])) if record else 0
    matches = [p for p in label_path.parent.iterdir() if p.name.lower() == name.group(1).lower()]
    if not matches:
        raise FileNotFoundError(f"{name.group(1)} not found next to {label_path.name}")
    return matches[0], offset
