"""Check Step 2's Sun and Earth positions (scripts/make_sky.py, NASA SPICE DE421) against NASA JPL Horizons.

JPL Horizons is the ephemeris service the challenge lists in its Resources tab. For every named site
(named_sites.csv) it is asked where the Sun and Earth are, seen from that point on the Moon's surface, at ten hours
spread over 2026-2030 and at the site's real landing hour (IM-1, IM-2). The same hours go through make_sky(), the
code the pipeline uses, and the two answers are compared.

Horizons query: observer table, CENTER = 'coord@301' (a point on the Moon), geodetic site on the Moon's mean-Earth
frame (the frame LOLA uses), QUANTITIES = 4 (apparent azimuth and elevation), APPARENT = 'AIRLESS' (no refraction),
times in UT. Horizons azimuth A is clockwise from local north; the team's theta is converted with A = (90 - lon) -
theta (make_sky.az_el_theta). Both sides use the site on the reference sphere (height 0): a few km of height moves
the Sun by under 0.0001 deg and Earth by under 0.0002 deg.

Fails (exit 1) if any azimuth or elevation differs by more than --tol degrees (default 0.01: a twentieth of the
Sun's radius). Writes every row to --out.

Usage:
  python scripts/validate_horizons.py --sites named_sites.csv --out out/validate_horizons.json
"""
import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.make_sky import load_kernels, make_sky  # noqa: E402

API = "https://ssd.jpl.nasa.gov/api/horizons.api"
BODIES = {"sun": "10", "earth": "399"}
TIMES = ("2026-01-01T00", "2026-07-15T06", "2027-01-28T12", "2027-08-10T18", "2028-02-22T03",
         "2028-09-05T09", "2029-03-20T15", "2029-10-02T21", "2030-04-16T01", "2030-11-29T13")


def julian_date(utc):
    """'YYYY-MM-DDTHH' (UTC) -> Julian date."""
    return (np.datetime64(utc) - np.datetime64("1970-01-01T00")) / np.timedelta64(1, "h") / 24 + 2440587.5


def horizons_url(body, lat, lon, times):
    q = {"format": "json", "COMMAND": f"'{BODIES[body]}'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'coord@301'",
         "COORD_TYPE": "'GEODETIC'", "SITE_COORD": f"'{lon % 360:.6f},{lat:.6f},0'",
         "TLIST": " ".join(f"'{julian_date(t):.8f}'" for t in times), "TLIST_TYPE": "'JD'", "TIME_TYPE": "'UT'",
         "QUANTITIES": "'4'", "ANG_FORMAT": "'DEG'", "APPARENT": "'AIRLESS'", "CSV_FORMAT": "'YES'"}
    return API + "?" + urllib.parse.urlencode(q)


def parse_table(result, times):
    """Horizons result text -> azimuth, elevation (deg) for `times` (sorted, 'YYYY-MM-DDTHH'); fails if Horizons
    answered for other times."""
    if "$$SOE" not in result:
        raise ValueError("Horizons returned no table:\n" + result[-800:])
    rows = [line.split(",") for line in result.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()]
    got = [_horizons_hour(r[0]) for r in rows]
    if got != list(times):
        raise ValueError(f"Horizons answered for {got}, asked for {list(times)}")
    return np.array([float(r[3]) for r in rows]), np.array([float(r[4]) for r in rows])


MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def _horizons_hour(stamp):
    """' 2024-Feb-22 23:00:00.000' -> '2024-02-22T23'."""
    day, clock = stamp.split()
    y, mon, d = day.split("-")
    return f"{y}-{MONTHS[mon]:02d}-{d}T{clock[:2]}"


def ask_horizons(body, lat, lon, times):
    with urllib.request.urlopen(horizons_url(body, lat, lon, times), timeout=120) as r:
        return parse_table(json.load(r)["result"], times)


def ours(lat, lon, times):
    """make_sky() at each hour -> {body: (azimuth clockwise from north, elevation)}, [sites, times], degrees."""
    n = lat.size
    out = {b: (np.empty((n, len(times))), np.empty((n, len(times)))) for b in BODIES}
    for j, t in enumerate(times):
        day, hour = t[:10], int(t[11:13])
        _, s_th, s_el, e_th, e_el, _, _ = make_sky(np.arange(n).astype(str), lat, lon, np.zeros(n), day, hour + 1)
        for b, th, el in (("sun", s_th, s_el), ("earth", e_th, e_el)):
            out[b][0][:, j] = (90.0 - lon - th[:, -1].astype(float)) % 360.0
            out[b][1][:, j] = el[:, -1]
    return out


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", default="named_sites.csv", help="CSV with id, name, lat, lon and optional landed_utc")
    ap.add_argument("--kernels", default="data/kernels")
    ap.add_argument("--tol", type=float, default=0.01, help="largest allowed difference, deg")
    ap.add_argument("--out", default="out/validate_horizons.json")
    a = ap.parse_args()

    with open(a.sites, newline="") as f:
        sites = list(csv.DictReader(f))
    lat = np.array([float(s["lat"]) for s in sites])
    lon = np.array([float(s["lon"]) for s in sites])
    per_site = [sorted(set(TIMES) | ({s["landed_utc"]} if s.get("landed_utc") else set())) for s in sites]
    all_times = sorted(set().union(*per_site))

    load_kernels(a.kernels)
    mine = ours(lat, lon, all_times)
    rows, worst = [], {(b, q): 0.0 for b in BODIES for q in ("az", "el")}
    for i, s in enumerate(sites):
        cols = [all_times.index(t) for t in per_site[i]]
        for b in BODIES:
            az_h, el_h = ask_horizons(b, lat[i], lon[i], per_site[i])
            for k, t in enumerate(per_site[i]):
                d_az = wrap(mine[b][0][i, cols[k]] - az_h[k])
                d_el = mine[b][1][i, cols[k]] - el_h[k]
                worst[b, "az"], worst[b, "el"] = max(worst[b, "az"], abs(d_az)), max(worst[b, "el"], abs(d_el))
                rows.append({"site": s["id"], "body": b, "utc": t, "horizons_az": az_h[k], "horizons_el": el_h[k],
                             "ours_az": round(float(mine[b][0][i, cols[k]]), 6),
                             "ours_el": round(float(mine[b][1][i, cols[k]]), 6),
                             "d_az": round(float(d_az), 6), "d_el": round(float(d_el), 6)})

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    summary = {f"{b}_{q}_max_deg": round(v, 6) for (b, q), v in worst.items()}
    Path(a.out).write_text(json.dumps({"source": "NASA JPL Horizons API vs scripts/make_sky.py (NASA SPICE, DE421)",
                                       "tol_deg": a.tol, "n_sites": len(sites), "n_rows": len(rows),
                                       "summary": summary, "rows": rows}, indent=1))
    print(f"{len(sites)} sites, {len(rows)} positions checked against JPL Horizons -> {a.out}")
    for (b, q), v in worst.items():
        print(f"  {b:5} {q}: worst difference {v:.6f} deg")
    if max(worst.values()) > a.tol:
        sys.exit(f"FAIL: a difference exceeds {a.tol} deg")
    print(f"OK: every difference is within {a.tol} deg")


if __name__ == "__main__":
    main()
