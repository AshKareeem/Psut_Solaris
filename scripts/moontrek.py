"""Download a window of NASA Moon Trek's 5 m LOLA south-pole elevation map around a site (challenge Resources tab).

Moon Trek (https://trek.nasa.gov/moon/) serves "LRO LOLA DEM, 87.5 deg v4, S Pole" (5 m per pixel, 87.5-90 S,
heights referred to a radius of 1737400 m) through an ArcGIS image service. Its map is the pipeline's own: south
polar stereographic on the 1737.4 km sphere (horizon/dem.py checks it). The window is aligned to the service's 5 m
pixel grid and read with nearest-neighbour sampling, so the file holds Moon Trek's own pixels, not resampled ones.

Needles: this older product holds isolated spikes from bad laser returns (around site 190, 10 pixels stand over
100 m above their neighbours; one is a 210 m needle 30 m wide, 582 m from the site, which alone would invent a 7 deg
skyline and a 4-hour shadow). A skyline is the highest terrain in each direction, so one needle fakes a shadow.
despike() replaces every pixel more than SPIKE_M above or below the median of the ring of pixels 3 away by that
median; the raw download is kept as <out>_raw.tif and the sidecar <out>.json records the count. Around site 190 that
is 0.12% of pixels, and a 30 m limit (0.96%) gives the same verdict, so the result does not hinge on the limit.

The cleaned file feeds scripts/analyze.py --near as the finest terrain level (5 m near the site, then 20 m, then
240 m). For site 190's demo mission it gives the same verdict as the 20 m map (Sun 100%, Earth 97%, survives).

Compared with the 20 m PDS map around site 190 (2 x 2 km, 4 x 4 blocks of 5 m pixels vs each 20 m pixel): median
difference 1.2 m on slopes under 5 deg, 2.2 m at 5-10 deg, 8 m on walls over 20 deg: the same LOLA measurements
gridded at two resolutions.

Photo: photo() stitches Moon Trek's "LRO NAC Mosaic, S Pole" (LROC Narrow Angle Camera, WMTS tiles) around a site
and circles the 100 m landing-error zone. The tile grid comes from the service's capabilities: top-left corner
(-1095930, 1095930) m, pixel = scale denominator x 0.28 mm (8562 m at level 0, halving per level; level 12 is
2.09 m). Checked against LOLA: Shackleton's shadowed interior is centred on LOLA's crater centre.

Usage:
  python scripts/moontrek.py --lat -89.79293 --lon -153.9246 --half-km 4.5 --out data/moontrek/site190_5m.tif
  python scripts/moontrek.py --lat -89.79293 --lon -153.9246 --half-km 2 --photo out/moontrek/site190_nac.png
"""
import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import io

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import latlon_to_xy, read_polar_geotiff  # noqa: E402

SERVICE = "https://trek.nasa.gov/moon/trekarcgis/rest/services/{product}/ImageServer"
PRODUCT = "LRO_LOLA_DEM_SPole875_5mp_v04"
PIXEL = 5.0
EXTENT = 75840.0          # the product covers x and y in [-75840, 75840] m
MAX_PIXELS = 4100         # the service's largest image side
NAC_TILES = "https://trek.nasa.gov/tiles/Moon/SP/LRO_NAC_Mosaic_1mpp_SP/1.0.0//default/default028mm/{z}/{r}/{c}.png"
NAC_ORIGIN = 1095930.0                       # top-left corner (-NAC_ORIGIN, NAC_ORIGIN), map metres
NAC_PIXEL0 = 3.0578404017857101e7 * 0.00028  # metres per pixel at level 0 (scale denominator x 0.28 mm)
NAC_MAX_LEVEL = 12
SPIKE_M = 50.0            # a pixel this far from its ring median is a needle (a 79 deg wall over 10 m: not terrain)


def despike(height, limit=SPIKE_M):
    """Replace pixels more than `limit` m from the median of the ring 3 pixels away by that median.
    Returns the cleaned heights and the number of pixels replaced."""
    z = height.astype(np.float64)
    w = sliding_window_view(np.pad(z, 3, mode="edge"), (7, 7))
    ring = np.concatenate([w[..., 0, :], w[..., -1, :], w[..., 1:-1, 0], w[..., 1:-1, -1]], axis=-1)
    med = np.median(ring, axis=-1)
    spike = np.abs(z - med) > limit
    return np.where(spike, med, z).astype(np.float32), int(spike.sum())


def window(x, y, half):
    """Map bounds (x_min, y_min, x_max, y_max) on the product's pixel grid holding every point within half m."""
    snap = lambda v, f: f(v / PIXEL) * PIXEL
    b =(snap(x - half, math.floor), snap(y - half, math.floor), snap(x + half, math.ceil), snap(y + half, math.ceil))
    if min(b) < -EXTENT or max(b) > EXTENT:
        raise ValueError(f"window {b} leaves the 5 m map (87.5-90 S, |x|, |y| <= {EXTENT:.0f} m)")
    if (b[2] - b[0]) / PIXEL > MAX_PIXELS or (b[3] - b[1]) / PIXEL > MAX_PIXELS:
        raise ValueError(f"window wider than {MAX_PIXELS} pixels ({MAX_PIXELS * PIXEL / 1e3:.1f} km); ask for less")
    return b


def export_url(bounds, product=PRODUCT):
    w, h = int(round((bounds[2] - bounds[0]) / PIXEL)), int(round((bounds[3] - bounds[1]) / PIXEL))
    q = {"bbox": ",".join(f"{v:.0f}" for v in bounds), "size": f"{w},{h}", "format": "tiff", "pixelType": "F32",
         "interpolation": "RSP_NearestNeighbor", "f": "image"}
    return SERVICE.format(product=product) + "/exportImage?" + urllib.parse.urlencode(q)


def fetch(lat, lon, half, out):
    x, y = latlon_to_xy(lat, lon)
    url = export_url(window(float(x), float(y), half))
    out = Path(out)
    raw = out.with_name(out.stem + "_raw.tif")
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        raw.write_bytes(r.read())
    dem = read_polar_geotiff(raw)                      # fails fast if it is not the expected map
    if dem.pixel != PIXEL:
        raise ValueError(f"{raw}: {dem.pixel} m pixels, expected {PIXEL}")
    clean, n_spikes = despike(dem.height)
    with rasterio.open(raw) as src:
        profile = src.profile
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(clean, 1)
    out.with_suffix(".json").write_text(json.dumps(
        {"source": "NASA Moon Trek (trek.nasa.gov/moon), " + PRODUCT, "url": url, "lat": lat, "lon": lon,
         "half_m": half, "shape": list(dem.height.shape), "raw_file": raw.name,
         "despike": {"limit_m": SPIKE_M, "pixels_replaced": n_spikes,
                     "share": round(n_spikes / dem.height.size, 5)},
         "heights": "metres above the 1737400 m reference sphere (Moon Trek product description)"}, indent=1))
    return read_polar_geotiff(out), n_spikes


def tile_span(x, y, half, level):
    """Pixel size (m) and the tile columns and rows (inclusive) covering x +- half, y +- half at this level."""
    px = NAC_PIXEL0 / 2 ** level
    tm = 256 * px
    cols = math.floor((x - half + NAC_ORIGIN) / tm), math.floor((x + half + NAC_ORIGIN) / tm)
    rows = math.floor((NAC_ORIGIN - (y + half)) / tm), math.floor((NAC_ORIGIN - (y - half)) / tm)
    return px, cols, rows


def photo(lat, lon, half, out, ring_m=100.0):
    """LROC NAC image of x +- half around the site from Moon Trek, the landing-error ring drawn on it."""
    x, y = (float(v) for v in latlon_to_xy(lat, lon))
    level = min(NAC_MAX_LEVEL, max(0, math.floor(math.log2(NAC_PIXEL0 * 1000 / (2 * half)))))   # ~1000+ px across
    px, (c0, c1), (r0, r1) = tile_span(x, y, half, level)
    canvas = Image.new("L", ((c1 - c0 + 1) * 256, (r1 - r0 + 1) * 256))
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            with urllib.request.urlopen(NAC_TILES.format(z=level, r=r, c=c), timeout=60) as resp:
                canvas.paste(Image.open(io.BytesIO(resp.read())).convert("L"), ((c - c0) * 256, (r - r0) * 256))
    left = (x - half + NAC_ORIGIN) / px - c0 * 256
    top = (NAC_ORIGIN - (y + half)) / px - r0 * 256
    img = canvas.crop((round(left), round(top), round(left + 2 * half / px), round(top + 2 * half / px))).convert("RGB")
    d, cx, cy, rr = ImageDraw.Draw(img), img.width / 2, img.height / 2, ring_m / px
    d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 160, 0), width=max(2, img.width // 400))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return img.size, px


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--half-km", type=float, default=4.5, help="half-width of the window (km)")
    ap.add_argument("--out", help="GeoTIFF to write (a .json sidecar goes next to it)")
    ap.add_argument("--photo", help="PNG to write: the LROC NAC image of the window, landing-error ring drawn")
    a = ap.parse_args()
    if bool(a.out) == bool(a.photo):
        ap.error("give exactly one of --out (elevation) and --photo (image)")
    if a.photo:
        size, px = photo(a.lat, a.lon, a.half_km * 1e3, a.photo)
        print(f"Moon Trek LRO NAC mosaic: {size[0]} x {size[1]} pixels of {px:.2f} m, 100 m ring drawn -> {a.photo}")
        return
    dem, n_spikes = fetch(a.lat, a.lon, a.half_km * 1e3, a.out)
    print(f"Moon Trek {PRODUCT}: {dem.height.shape[1]} x {dem.height.shape[0]} pixels of {dem.pixel:g} m, "
          f"{n_spikes} needles (> {SPIKE_M:g} m off their neighbours) replaced, heights "
          f"{float(dem.height.min()):.1f} to {float(dem.height.max()):.1f} m -> {a.out}")


if __name__ == "__main__":
    main()
