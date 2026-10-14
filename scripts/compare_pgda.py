"""Read NASA's published illumination (or Earth-visibility) map at one site, to compare with our engine.

Download from NASA PGDA (Lunar Polar Illumination, https://pgda.gsfc.nasa.gov/products/69):
  https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF        (Sun)
  https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF  (Earth)

A site taken from the 240 m grid sits exactly on a corner of four 60 m pixels, so "the pixel at the site" is
arbitrary there; the script says so and prints the pixels touching it. scripts/validate_pgda.py compares at pixel
centres instead.

Usage:
  python scripts/compare_pgda.py data/AVGVISIB_85S_060M_201608.TIF --lat -89.778601 --lon -155.72556
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import Window

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import latlon_to_xy  # noqa: E402

MOON_LONLAT = "+proj=longlat +R=1737400 +no_defs"


def read_window(tif_path, lat, lon, n):
    """NASA's values (scale and offset applied) for the n x n pixels around (lat, lon), and their centres' lat, lon.

    Odd n centres the window on the pixel holding the site, even n on the pixel corner nearest it. info holds the
    map's metadata, the site's x, y in the map's projection and its pixel position (col, row); whole numbers are edges.
    """
    with rasterio.open(tif_path) as src:
        if src.crs is None:
            raise ValueError(f"{tif_path} has no map projection")
        to_map = Transformer.from_crs(MOON_LONLAT, src.crs, always_xy=True)
        x, y = to_map.transform(lon, lat)
        col, row = ~src.transform @ (x, y)
        c0, r0 = int(np.floor(col - n / 2 + 0.5)), int(np.floor(row - n / 2 + 0.5))
        values = src.read(1, window=Window(c0, r0, n, n), masked=True).astype(float) * src.scales[0] + src.offsets[0]
        if values.shape != (n, n):
            raise ValueError(f"the {n} x {n} window around {lat}, {lon} runs off {tif_path}")
        cols, rows = np.meshgrid(np.arange(c0, c0 + n) + 0.5, np.arange(r0, r0 + n) + 0.5)
        lon_c, lat_c = to_map.transform(*(src.transform @ (cols, rows)), direction="INVERSE")
        info = {"crs": src.crs.to_string(), "pixel_m": src.res[0], "scale": src.scales[0],
                "offset": src.offsets[0], "nodata": src.nodata, "dtype": src.dtypes[0],
                "tags": {**src.tags(), **src.tags(1)}, "site_xy": (x, y), "site_pixel": (col, row)}
    return values, lat_c, lon_c, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tif")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=int, default=2, help="neighbourhood half-size in pixels")
    args = ap.parse_args()

    block, _, _, info = read_window(args.tif, args.lat, args.lon, 2 * args.radius + 1)
    (x, y), (col, row) = info["site_xy"], info["site_pixel"]
    ox, oy = latlon_to_xy(args.lat, args.lon)
    print(f"map: {info['crs']}")
    print(f"pixel {info['pixel_m']} m | dtype {info['dtype']} | scale {info['scale']} | offset {info['offset']} "
          f"| nodata {info['nodata']}")
    if info["tags"]:
        print(f"metadata: {info['tags']}")
    print(f"site x, y from the map's projection: {x:.1f}, {y:.1f} m | from our engine: {ox:.1f}, {oy:.1f} m")
    if np.hypot(x - ox, y - oy) > 1:
        print("WARNING: the map's projection and ours disagree by more than 1 m. Stop and check.")
    print(f"value at the site: {block[args.radius, args.radius]:.4f}")
    edge = min(abs(col - round(col)), abs(row - round(row))) * info["pixel_m"]
    if edge < 1:
        touching = read_window(args.tif, args.lat, args.lon, 2)[0]
        print(f"WARNING: the site is {edge:.2f} m from a pixel edge, so 'the pixel at the site' is arbitrary. "
              f"The 2 x 2 pixels around its nearest corner: {np.round(touching, 4).tolist()}")
    print(f"neighbourhood ({block.shape[0]}x{block.shape[1]} px): min {block.min():.4f}, "
          f"mean {block.mean():.4f}, max {block.max():.4f}")
    print("If values run 0-1 they are fractions of time (x100 for %); check the metadata above.")


if __name__ == "__main__":
    main()
