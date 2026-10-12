"""Read LOLA south-polar DEMs (PDS3 .LBL + .IMG) and convert between lat/lon and grid positions.

Map convention (PDS polar stereographic, south pole):
  - the pole is at the centre of a square grid
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
    center: float       # row and column index of the pole (the grid is square)

    def latlon_to_rowcol(self, lat_deg, lon_deg):
        x, y = latlon_to_xy(lat_deg, lon_deg)
        return self.center - y / self.pixel, self.center + x / self.pixel

    def rowcol_to_latlon(self, row, col):
        x = (np.asarray(col) - self.center) * self.pixel
        y = (self.center - np.asarray(row)) * self.pixel
        return xy_to_latlon(x, y)


def latlon_to_xy(lat_deg, lon_deg):
    """South polar stereographic on the 1737.4 km sphere, true scale at the pole. Metres."""
    rho = 2 * R * np.tan(np.radians(90 + np.asarray(lat_deg)) / 2)
    lon = np.radians(lon_deg)
    return rho * np.sin(lon), rho * np.cos(lon)


def xy_to_latlon(x, y):
    rho = np.hypot(x, y)
    return -90 + np.degrees(2 * np.arctan(rho / (2 * R))), np.degrees(np.arctan2(x, y))


def read_polar_dem(label_path):
    """Load a south-polar LOLA DEM from its PDS3 label. Fails fast on anything unexpected."""
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
    dn = np.fromfile(img_path, dtype=dtype, count=n * n, offset=byte_offset)
    if dn.size != n * n:
        raise ValueError(f"{img_path.name} is too short: {dn.size} of {n * n} samples")
    height = (dn.astype(np.float32) * np.float32(_number(lbl["SCALING_FACTOR"]))).reshape(n, n)
    if "MISSING_CONSTANT" in lbl:
        height[dn.reshape(n, n) == _number(lbl["MISSING_CONSTANT"])] = np.nan

    return PolarDEM(height=height, pixel=_metres(lbl["MAP_SCALE"]), center=center)


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
