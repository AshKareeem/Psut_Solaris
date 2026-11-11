"""
Independent check of sky.npz (CE 2, Step 2) with a second astronomy library, Skyfield.

scripts/make_sky.py uses SpiceyPy (NASA's SPICE toolkit). Skyfield is written by different people with its own
frame, light-time and aberration code. If both give the same Sun and Earth directions and heights, the numbers
are right, not just consistent with themselves.

Run, after scripts/make_sky.py has made sky.npz (and downloaded data/kernels/):
  python scripts/validate_sky_skyfield.py --sky sky.npz --heights sites.csv

Pass rule: every compared value within 0.001 deg.
"""
import argparse
import sys

import numpy as np

try:
    from skyfield.api import Loader, load
    from skyfield.planetarylib import PlanetaryConstants
except ImportError:
    sys.exit("skyfield is missing. Run:  pip install skyfield")

TOL_DEG = 0.001


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sky", default="sky.npz")
    ap.add_argument("--kernels", default="data/kernels", help="folder with de421.bsp, moon_080317.tf, moon_pa_de421_1900-2050.bpc")
    ap.add_argument("--sites", type=int, default=8, help="how many sites to compare (spread through the file)")
    ap.add_argument("--hours", type=int, default=300, help="how many random time steps to compare")
    ap.add_argument("--heights", help="optional sites.csv to use each site's height (default 0 m; affects Earth by < 0.001 deg)")
    a = ap.parse_args()

    sky = np.load(a.sky)
    L = Loader(a.kernels)
    eph = L("de421.bsp")
    pc = PlanetaryConstants()
    pc.read_text(L("moon_080317.tf"))
    pc.read_binary(L("moon_pa_de421_1900-2050.bpc"))
    pc.variables["BODY301_RADII"] = [1737.4, 1737.4, 1737.4]    # the team's sphere, km (same as LOLA and the engine)
    frame = pc.build_frame_named("MOON_ME_DE421")
    moon, sun, earth = eph["moon"], eph["sun"], eph["earth"]
    ts = load.timescale(builtin=True)

    heights = None
    if a.heights:
        import pandas as pd
        df = pd.read_csv(a.heights)
        heights = dict(zip(df["id"].astype(str), df["height"].astype(float)))

    n_sites, n_t = sky["sun_az"].shape
    sites = np.unique(np.linspace(0, n_sites - 1, min(a.sites, n_sites)).astype(int))
    hrs = np.sort(np.random.default_rng(0).choice(n_t, min(a.hours, n_t), replace=False))
    dt = [np.datetime64(sky["time_utc"][k]).astype(object) for k in hrs]
    t = ts.utc([d.year for d in dt], [d.month for d in dt], [d.day for d in dt], [d.hour for d in dt])

    worst = {k: 0.0 for k in ("sun_az", "sun_el", "earth_az", "earth_el")}
    for si in sites:
        lat, lon = float(sky["site_lat"][si]), float(sky["site_lon"][si])
        h = heights.get(str(sky["site_id"][si]), 0.0) if heights else 0.0
        place = moon + pc.build_latlon_degrees(frame, lat, lon, elevation_m=h)
        for name, body in (("sun", sun), ("earth", earth)):
            alt, az, _ = place.at(t).observe(body).apparent().altaz()
            theta = (90.0 - lon - az.degrees) % 360.0          # same team convention
            worst[name + "_el"] = max(worst[name + "_el"], float(np.abs(sky[name + "_el"][si, hrs] - alt.degrees).max()))
            if abs(lat) < 89.9999:                              # azimuth is undefined exactly at the pole
                d = np.abs((sky[name + "_az"][si, hrs] - theta + 180.0) % 360.0 - 180.0)
                worst[name + "_az"] = max(worst[name + "_az"], float(d.max()))

    print(f"Compared {len(sites)} sites x {len(hrs)} time steps with Skyfield")
    ok = True
    for k, v in worst.items():
        passed = v <= TOL_DEG
        ok &= passed
        print(f"  {k:9s} worst difference {v:.5f} deg  {'PASS' if passed else 'FAIL'}")
    print("SKYFIELD CHECK PASSED" if ok else "SKYFIELD CHECK FAILED - tell the team before using sky.npz")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
