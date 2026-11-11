"""
CE 2 - Step 2: Sun and Earth positions for every site and every hour (sky.npz)
CLPS Lunar Mission Browser (LunarWindow) - NASA Space Apps 2026 - team Psut_Solaris
Version 4 (in the repo): fixed de421.bsp link, Sun and Earth angular radii per hour

What it does
  For each site in sites.csv and each hour, it uses NASA's SPICE toolkit to find
  where the Sun and Earth are in that site's sky:
    - elevation (degrees above the level horizon, the same level Ash's skylines use)
    - direction theta (degrees) in the TEAM convention:
        theta is measured from the map's +x axis, counterclockwise, 0-360.
        Longitude 0 is map up (theta = 90), 90E is map right (theta = 0).

  SPICE-style azimuth A is clockwise from local north. We convert it with
      theta = beta - A,   beta = 90 - lon  (direction of local north on the map)
  This is exact for the south polar stereographic map (lon_0 = 0) used by the engine.

Output: sky.npz
  site_id   [sites]          ids from sites.csv, same order
  site_lat, site_lon [sites] degrees, for checking the order
  time_utc  [hours]          'YYYY-MM-DDTHH:00:00' (UTC)
  sun_az, sun_el, earth_az, earth_el   [sites, hours] float32, degrees
  sun_radius_deg, earth_radius_deg     [hours] float32, apparent disc radius seen from the Moon
  source = 'SPICE', step_hours, frame, kernels, convention, script_version

Run:
  python scripts/make_sky.py --sites sites.csv --year 2027 --out sky.npz
"""

import argparse
import os
import sys
import urllib.request

import numpy as np

try:
    import spiceypy as sp
except ImportError:
    sys.exit("spiceypy is missing. Run:  pip install spiceypy")
try:
    import pandas as pd
except ImportError:
    sys.exit("pandas is missing. Run:  pip install pandas")

VERSION = "make_sky v4"
MOON_R_M = 1737400.0            # the map's sphere (+R=1737400), same as Ash's engine
FRAME = "MOON_ME_DE421"         # LOLA's frame: Mean Earth / polar axis of DE421
SUN_PERIOD_DAYS = 29.530589     # synodic month: the Sun circles a polar site once per period
SUN_R_M, EARTH_R_M = 695_700_000.0, 6_371_000.0   # IAU nominal solar radius, Earth's mean radius

NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
# name: (url, minimum size in bytes, to catch broken downloads)
KERNELS = {
    "naif0012.tls": (NAIF + "lsk/naif0012.tls", 1_000),
    "de421.bsp": (NAIF + "spk/planets/a_old_versions/de421.bsp", 16_000_000),   # NAIF moved it here
    "moon_pa_de421_1900-2050.bpc": (NAIF + "pck/moon_pa_de421_1900-2050.bpc", 1_700_000),
    "moon_080317.tf": (NAIF + "fk/satellites/moon_080317.tf", 15_000),
}
ET_FIRST, ET_LAST = "1900-01-02", "2049-12-30"   # coverage of de421 + the Moon orientation file


# ---------------------------------------------------------------- kernels
def load_kernels(folder):
    os.makedirs(folder, exist_ok=True)
    for name, (url, min_size) in KERNELS.items():
        path = os.path.join(folder, name)
        if not os.path.exists(path) or os.path.getsize(path) < min_size:
            print(f"downloading {name} ...")
            try:
                urllib.request.urlretrieve(url, path)
            except Exception as e:
                sys.exit(f"Could not download {name} from {url}\n{e}\n"
                         f"Download it by hand into {folder}/ and run again.")
            if os.path.getsize(path) < min_size:
                sys.exit(f"{name} looks incomplete ({os.path.getsize(path)} bytes). Delete it and run again.")
        sp.furnsh(path)
    print("SPICE kernels loaded:", ", ".join(KERNELS))


# ---------------------------------------------------------------- sites
def read_sites(path):
    df = pd.read_csv(path)
    cols = {c.strip().lower(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_id, c_lat, c_lon = pick("id", "site_id"), pick("lat", "lat_deg", "latitude"), pick("lon", "lon_deg", "longitude")
    c_h = pick("height", "height_m")
    missing = [n for n, c in [("id", c_id), ("lat", c_lat), ("lon", c_lon)] if c is None]
    if missing:
        sys.exit(f"sites.csv is missing column(s) {missing}. Found: {list(df.columns)}")
    if len(df) == 0:
        sys.exit("sites.csv has no sites.")

    ids = df[c_id].to_numpy()
    if len(set(ids.tolist())) != len(ids):
        sys.exit("sites.csv has duplicate ids.")
    lat = pd.to_numeric(df[c_lat], errors="coerce").to_numpy(float)
    lon = pd.to_numeric(df[c_lon], errors="coerce").to_numpy(float)
    if c_h is None:
        print("WARNING: no height column, using 0 m for every site.")
        h = np.zeros(len(df))
    else:
        h = pd.to_numeric(df[c_h], errors="coerce").to_numpy(float)

    bad = np.flatnonzero(~np.isfinite(lat) | ~np.isfinite(lon) | ~np.isfinite(h))
    if bad.size:
        sys.exit(f"sites.csv has empty or non-number lat/lon/height in rows {bad[:10].tolist()}")
    if (lat < -90).any() or (lat > 90).any():
        sys.exit("sites.csv has latitudes outside -90..90.")
    if (lat > 0).any():
        sys.exit("sites.csv has northern latitudes; this tool is for the south pole (lat must be negative).")
    if (np.abs(h) > 20_000).any():
        sys.exit("sites.csv has heights over 20 km; height must be metres above the 1737.4 km sphere.")
    far = np.flatnonzero(lat > -84.0)
    if far.size:
        print(f"WARNING: {far.size} sites are more than 6 deg from the pole (NASA's gate). Kept anyway.")
    lon = ((lon + 180.0) % 360.0) - 180.0      # accept 0..360 or -180..180
    return ids, lat, lon, h


# ---------------------------------------------------------------- geometry
def local_axes(lat_deg, lon_deg):
    """Unit up / east / north vectors (Moon body-fixed frame) for each site, on the sphere."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    up = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)
    east = np.stack([-np.sin(lon), np.cos(lon), np.zeros_like(lon)], axis=-1)
    north = np.cross(up, east)
    return up, east, north


def az_el_theta(vec, up, east, north, lon_deg):
    """vec [sites, hours, 3] from site to target. Returns theta (team convention) and elevation, degrees."""
    norm = np.linalg.norm(vec, axis=-1)
    u = np.einsum("shk,sk->sh", vec, up) / norm
    e = np.einsum("shk,sk->sh", vec, east)
    n = np.einsum("shk,sk->sh", vec, north)
    el = np.degrees(np.arcsin(np.clip(u, -1, 1)))
    A = np.degrees(np.arctan2(e, n)) % 360.0             # clockwise from local north
    theta = ((90.0 - lon_deg)[:, None] - A) % 360.0       # theta = beta - A
    theta = np.where(theta >= 360.0, 0.0, theta)
    return theta, el


# ---------------------------------------------------------------- main work
def time_axis(start, n_steps, step_h):
    t0 = np.datetime64(f"{start}T00:00:00")
    t_end = t0 + np.timedelta64((n_steps - 1) * step_h, "h")
    if t0 < np.datetime64(ET_FIRST) or t_end > np.datetime64(ET_LAST):
        sys.exit(f"Dates must be between {ET_FIRST} and {ET_LAST} (the NASA files' coverage).")
    times = np.array([str(t0 + np.timedelta64(k * step_h, "h")) for k in range(n_steps)])
    ets = np.array([sp.str2et(s) for s in times])
    return times, ets


def make_sky(ids, lat, lon, h, start, n_steps, step_h=1):
    times, ets = time_axis(start, n_steps, step_h)
    print(f"{len(ids)} sites x {n_steps} time steps ({step_h} h apart), frame {FRAME}")

    # Apparent Sun and Earth (light time + aberration) seen from the Moon's centre, km -> m
    sun = np.asarray(sp.spkpos("SUN", ets, FRAME, "LT+S", "MOON")[0]) * 1000.0
    earth = np.asarray(sp.spkpos("EARTH", ets, FRAME, "LT+S", "MOON")[0]) * 1000.0

    up, east, north = local_axes(lat, lon)
    site = up * (MOON_R_M + h)[:, None]

    shape = (len(ids), n_steps)
    sun_az, sun_el = np.empty(shape, np.float32), np.empty(shape, np.float32)
    earth_az, earth_el = np.empty(shape, np.float32), np.empty(shape, np.float32)
    chunk = max(1, int(2e7 // (n_steps * 3)))
    for i in range(0, len(ids), chunk):
        sl = slice(i, i + chunk)
        sun_az[sl], sun_el[sl] = az_el_theta(sun[None] - site[sl, None], up[sl], east[sl], north[sl], lon[sl])
        earth_az[sl], earth_el[sl] = az_el_theta(earth[None] - site[sl, None], up[sl], east[sl], north[sl], lon[sl])
    for a in (sun_az, earth_az):
        a[a >= 360.0] = 0.0                              # float32 rounding
    # apparent disc radii from the Moon's centre (a site 1737 km off-centre changes Earth's by < 0.005 deg)
    sun_r = np.degrees(np.arcsin(SUN_R_M / np.linalg.norm(sun, axis=1))).astype(np.float32)
    earth_r = np.degrees(np.arcsin(EARTH_R_M / np.linalg.norm(earth, axis=1))).astype(np.float32)
    return times, sun_az, sun_el, earth_az, earth_el, sun_r, earth_r


# ---------------------------------------------------------------- checks
def convention_test():
    """Ash's test_longitude_0_is_map_up_and_90E_is_map_right, for sites at many longitudes and at the pole."""
    far = 1e13
    targets = {90.0: [1, 0, 0], 0.0: [0, 1, 0], 270.0: [-1, 0, 0], 180.0: [0, -1, 0]}
    worst = 0.0
    # Sites near the pole, as in Ash's test (a far target "toward lon 0" sits exactly at theta 90
    # only at the pole; sites farther out are covered by the joint test with Ash's engine).
    for lat0, lon0 in [(-89.5, 0.0), (-89.5, 45.0), (-89.5, 90.0), (-89.5, -155.7), (-89.5, 180.0),
                       (-89.5, -60.0), (-90.0, 0.0), (-90.0, 77.0)]:
        lat, lon = np.array([lat0]), np.array([lon0])
        up, east, north = local_axes(lat, lon)
        site = up * MOON_R_M
        for expect, d in targets.items():
            th, _ = az_el_theta((np.array(d, float) * far - site)[:, None, :], up, east, north, lon)
            worst = max(worst, abs((float(th[0, 0]) - expect + 180.0) % 360.0 - 180.0))
    ok = worst < 0.01
    print(f"[check 0] direction convention (lon 0 = theta 90, 90E = theta 0): "
          f"{'PASS' if ok else 'FAIL'} (worst error {worst:.4f} deg)")
    if not ok:
        sys.exit("Direction convention is broken - stop and tell the team.")


def sanity_checks(lat, step_h, sun_az, sun_el, earth_az, earth_el):
    ok = True
    colat = 90.0 - np.abs(lat)

    def report(n, text, passed, detail):
        nonlocal ok
        ok &= bool(passed)
        print(f"[check {n}] {text}: {'PASS' if passed else 'FAIL'} ({detail})")

    finite = all(np.isfinite(a).all() for a in (sun_az, sun_el, earth_az, earth_el))
    in_range = all(((a >= 0) & (a < 360)).all() for a in (sun_az, earth_az))
    report(1, "no missing values, directions in 0-360", finite and in_range, "all values valid" if finite and in_range else "bad values found")

    # Sun: never higher than distance from the pole + the Moon's 1.54 deg tilt (+ margin)
    excess = (np.abs(sun_el).max(axis=1) - (colat + 1.6 + 0.3)).max()
    report(2, "Sun height within limits", excess <= 0, f"max |sun_el| {np.abs(sun_el).max():.2f} deg")

    # Earth: stays toward map up (theta ~ 90) and bobs about 6.7 deg (libration) plus distance from pole
    d = (earth_az - 90.0 + 180.0) % 360.0 - 180.0
    worst = float(np.abs(np.median(d, axis=1)).max())
    report(3, "Earth direction near theta = 90", worst < 15, f"worst site median offset {worst:.1f} deg")
    excess_e = (np.abs(earth_el).max(axis=1) - (colat + 7.5)).max()
    report(4, "Earth height within libration limits", excess_e <= 0,
           f"range {earth_el.min():.2f} to {earth_el.max():.2f} deg")

    # Sun circles the sky once per synodic month (checked at the site nearest the pole)
    span_days = sun_az.shape[1] * step_h / 24.0
    if span_days >= 2 * SUN_PERIOD_DAYS and step_h <= 6:
        i = int(np.argmax(np.abs(lat)))
        turns = np.abs(np.unwrap(np.radians(sun_az[i].astype(float)))[-1]
                       - np.radians(float(sun_az[i, 0]))) / (2 * np.pi)
        expect = span_days / SUN_PERIOD_DAYS
        report(5, "Sun circles the sky once per 29.5 days", abs(turns - expect) < 1.0,
               f"{turns:.2f} turns, expected {expect:.2f}")
    else:
        print("[check 5] Sun circling: skipped (needs 2+ months at 6 h steps or finer)")
    return ok


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="CE 2: Sun and Earth positions per site per hour (sky.npz)")
    ap.add_argument("--sites", required=True, help="sites.csv with id, lat, lon and height (m)")
    ap.add_argument("--year", type=int, default=2027, help="whole calendar year, hourly (default 2027)")
    ap.add_argument("--start", help="custom start date YYYY-MM-DD (overrides --year)")
    ap.add_argument("--days", type=float, help="custom length in days (needed with --start)")
    ap.add_argument("--step", type=int, default=1, help="hours between samples (default 1)")
    ap.add_argument("--kernels", default="data/kernels", help="folder for the NASA SPICE files")
    ap.add_argument("--out", default="sky.npz")
    a = ap.parse_args()
    if a.step < 1:
        sys.exit("--step must be 1 or more")

    print(VERSION)
    convention_test()
    ids, lat, lon, h = read_sites(a.sites)
    if a.start:
        if not a.days or a.days <= 0:
            sys.exit("--start needs a positive --days")
        start, n_steps = a.start, int(a.days * 24 // a.step)
    else:
        start = f"{a.year}-01-01"
        n_days = int((np.datetime64(f"{a.year + 1}-01-01") - np.datetime64(start)).astype(int))
        n_steps = n_days * 24 // a.step
    est_mb = len(ids) * n_steps * 16 / 1e6
    print(f"{len(ids)} sites read. Expected size before compression: about {est_mb:,.0f} MB")
    if est_mb > 2000:
        print("WARNING: very large. Ask CE 3 if a smaller site list or a bigger --step is fine.")

    load_kernels(a.kernels)
    times, sun_az, sun_el, earth_az, earth_el, sun_r, earth_r = make_sky(ids, lat, lon, h, start, n_steps, a.step)
    ok = sanity_checks(lat, a.step, sun_az, sun_el, earth_az, earth_el)
    print(f"disc radii: Sun {sun_r.min():.3f}-{sun_r.max():.3f} deg, Earth {earth_r.min():.3f}-{earth_r.max():.3f} deg")

    np.savez_compressed(
        a.out,
        site_id=ids, site_lat=lat, site_lon=lon, time_utc=times,
        sun_az=sun_az, sun_el=sun_el, earth_az=earth_az, earth_el=earth_el,
        sun_radius_deg=sun_r, earth_radius_deg=earth_r,
        source=np.array("SPICE"), step_hours=np.array(a.step),
        frame=np.array(FRAME), kernels=np.array(list(KERNELS)), script_version=np.array(VERSION),
        convention=np.array("theta from map +x, counterclockwise, 0-360 deg; lon 0 = map up (90), "
                            "90E = map right (0); elevation above the level plane of the 1737.4 km sphere; "
                            "UTC; apparent centres of the Sun and Earth (LT+S)"),
    )
    print(f"\nWrote {a.out}: {sun_az.shape[0]} sites x {sun_az.shape[1]} time steps")
    print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED - do not hand this file to CE 3 yet")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
