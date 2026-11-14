"""Build the web app's files in web/: the Moon textures for the globe and a copy of the pipeline's results.

  web/assets/moon_color.jpg   NASA SVS CGI Moon Kit colour map (LRO LROC WAC, 4096 x 2048, equirectangular,
                              longitude -180..180 left to right, north up)
  web/assets/moon_relief.png  slopes of the CGI Moon Kit elevation map (LOLA, 4 px/deg): R = east slope,
                              G = north slope, 128 + SLOPE_SCALE x slope (rise over run), for the globe's lighting
  web/data/results.json       scripts/score_sites.py output (version 4) for the default lander preset
  web/data/sites/<id>_<mast>.json  scripts/site_report.py output: each ranked site's mission at each height
  web/data/profiles/<id>/     the same two for every other lander preset (scripts/profiles.py)
  web/data/profiles.json      the presets: id, label, description, results (path of its results.json), default
  web/data/named_sites.json   named_sites.csv (presets for the mission panel)
  web/data/region.json        the whole region (scripts/run_region.py): counts and the best sites per mast

Sources (download once into data/moon/): https://svs.gsfc.nasa.gov/4720
  lroc_color_poles_4k.tif, ldem_4.tif

Usage:
  python scripts/build_web.py --profiles out/profiles_failsafe --region out/region/region_summary.json
"""
import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.profiles import DEFAULT, PROFILES  # noqa: E402

R_KM = 1737.4
SLOPE_SCALE = 508.0          # slope 0.25 (14 deg) -> 127 counts; steeper slopes are rare at 7.6 km pixels
ROOT = Path(__file__).resolve().parents[1]


def moon_color(src, dst):
    with rasterio.open(src) as r:
        rgb = np.moveaxis(r.read(), 0, -1)
    Image.fromarray(rgb).save(dst, quality=86, optimize=True, progressive=True)


def moon_relief(src, dst):
    """East and north slopes (dimensionless) of an equirectangular elevation map in km."""
    with rasterio.open(src) as r:
        z = r.read(1).astype(np.float64)
    rows, cols = z.shape
    step = np.radians(360.0 / cols)                                   # radians per pixel, both axes
    lat = np.radians(90.0 - (np.arange(rows) + 0.5) * 180.0 / rows)[:, None]
    east = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2 * R_KM * step * np.maximum(np.cos(lat), 0.02))
    north = np.empty_like(z)
    north[1:-1] = (z[:-2] - z[2:]) / (2 * R_KM * step)               # row 0 is north
    north[0], north[-1] = north[1], north[-2]
    enc = lambda s: np.clip(np.round(128 + SLOPE_SCALE * s), 0, 255).astype(np.uint8)
    rgb = np.stack([enc(east), enc(north), np.full(z.shape, 128, np.uint8)], axis=-1)
    Image.fromarray(rgb).save(dst, optimize=True)


def copy_results(results_dir, data_dir):
    """results.json and every detail file it names; fails if one is missing."""
    results = json.loads((results_dir / "results.json").read_text())
    if results["meta"]["version"] != 4:
        raise ValueError(f"{results_dir / 'results.json'} is version {results['meta']['version']}, the app reads 4")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    (data_dir / "sites").mkdir(parents=True)
    shutil.copy(results_dir / "results.json", data_dir / "results.json")
    files = [e["detail_file"] for s in results["sites"] for e in s["masts"].values() if e["detail_file"]]
    for f in files:
        shutil.copy(results_dir / f, data_dir / f)
    return len(files)


def copy_profiles(profiles_dir, data_dir):
    """Every preset's results (the default at data_dir, the others under data_dir/profiles/<id>) and the index
    profiles.json; fails if a preset is missing or its results.json was made with another preset."""
    index = []
    for pid in [DEFAULT] + [p for p in PROFILES if p != DEFAULT]:     # the default first: it clears data_dir
        src = Path(profiles_dir) / pid
        made_with = json.loads((src / "results.json").read_text())["meta"].get("profile", {}).get("id")
        if made_with != pid:
            raise ValueError(f"{src / 'results.json'} was made with preset {made_with!r}, expected {pid!r}")
        rel = Path() if pid == DEFAULT else Path("profiles") / pid
        copy_results(src, data_dir / rel)
        index.append({"id": pid, "label": PROFILES[pid]["label"], "description": PROFILES[pid]["description"],
                      "payloads": PROFILES[pid]["payloads"],
                      "results": (rel / "results.json").as_posix(), "default": pid == DEFAULT})
    (data_dir / "profiles.json").write_text(json.dumps(index, indent=1))
    return len(index)


def named_sites(src, dst):
    """named_sites.csv as JSON for the mission panel's presets (coordinates, citation, real landing hour)."""
    with open(src, newline="") as f:
        rows = [{**r, "lat": float(r["lat"]), "lon": float(r["lon"])} for r in csv.DictReader(f)]
    dst.write_text(json.dumps(rows, indent=1))
    return len(rows)


def region(src, dst, top=8):
    """scripts/run_region.py's summary, cut to the counts and the best `top` sites per mast, for the page."""
    r = json.loads(Path(src).read_text())
    keep = {k: r[k] for k in ("sites", "pass_gates", "sites_with_a_safe_day", "span", "ranking_keys")}
    keep["best_by_mast"] = {m: lst[:top] for m, lst in r["ranked_by_mast"].items()}
    keep["checked_100m_by_mast"] = {m: sum(1 for s in lst if (s["safe_days_within_100m"] or 0) > 0)
                                    for m, lst in r["ranked_by_mast"].items()}
    dst.write_text(json.dumps(keep, indent=1))
    return r["sites"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", required=True, help="scripts/run_profiles.py output: one folder per preset")
    ap.add_argument("--region", required=True, help="scripts/run_region.py region_summary.json")
    ap.add_argument("--moon", default=str(ROOT / "data/moon"), help="folder with the two CGI Moon Kit files")
    ap.add_argument("--web", default=str(ROOT / "web"))
    a = ap.parse_args()

    web, moon = Path(a.web), Path(a.moon)
    (web / "assets").mkdir(parents=True, exist_ok=True)
    moon_color(moon / "lroc_color_poles_4k.tif", web / "assets/moon_color.jpg")
    moon_relief(moon / "ldem_4.tif", web / "assets/moon_relief.png")
    n = copy_profiles(Path(a.profiles), web / "data")
    k = named_sites(ROOT / "named_sites.csv", web / "data/named_sites.json")
    nr = region(a.region, web / "data/region.json")
    print(f"web/assets: moon_color.jpg, moon_relief.png; web/data: {n} lander presets (profiles.json), "
          f"{k} named sites, the region ({nr} sites)")


if __name__ == "__main__":
    main()
