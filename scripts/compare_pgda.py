"""Read NASA's published illumination (or Earth-visibility) map at one site, to compare with our engine.

Download from NASA PGDA (Lunar Polar Illumination, https://pgda.gsfc.nasa.gov/products/69):
  https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF        (Sun)
  https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF  (Earth)

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


def read_site(tif_path, lat, lon, radius):
    """Value at the site and its (2*radius+1)^2 neighbourhood, with the map's scale/offset applied."""
    with rasterio.open(tif_path) as src:
        if src.crs is None:
            raise ValueError(f"{tif_path} has no map projection")
        x, y = Transformer.from_crs(MOON_LONLAT, src.crs, always_xy=True).transform(lon, lat)
        row, col = src.index(x, y)
        window = Window(col - radius, row - radius, 2 * radius + 1, 2 * radius + 1)
        block = src.read(1, window=window, masked=True).astype(float) * src.scales[0] + src.offsets[0]
        info = {"crs": src.crs.to_string(), "pixel_m": src.res[0], "scale": src.scales[0],
                "offset": src.offsets[0], "nodata": src.nodata, "dtype": src.dtypes[0],
                "tags": {**src.tags(), **src.tags(1)}}
    return block, (x, y), info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tif")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=int, default=2, help="neighbourhood half-size in pixels")
    args = ap.parse_args()

    block, (x, y), info = read_site(args.tif, args.lat, args.lon, args.radius)
    ox, oy = latlon_to_xy(args.lat, args.lon)
    print(f"map: {info['crs']}")
    print(f"pixel {info['pixel_m']} m | dtype {info['dtype']} | scale {info['scale']} | offset {info['offset']} "
          f"| nodata {info['nodata']}")
    if info["tags"]:
        print(f"metadata: {info['tags']}")
    print(f"site x, y from the map's projection: {x:.1f}, {y:.1f} m | from our engine: {ox:.1f}, {oy:.1f} m")
    if np.hypot(x - ox, y - oy) > 1:
        print("WARNING: the map's projection and ours disagree by more than 1 m. Stop and check.")
    centre = block[args.radius, args.radius]
    print(f"value at the site: {centre:.4f}")
    print(f"neighbourhood ({block.shape[0]}x{block.shape[1]} px): min {block.min():.4f}, "
          f"mean {block.mean():.4f}, max {block.max():.4f}")
    print("If values run 0-1 they are fractions of time (x100 for %); check the metadata above.")


if __name__ == "__main__":
    main()
