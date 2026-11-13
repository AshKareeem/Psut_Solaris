"""Steps 3-4 (CE 3): visibility, safe landing dates, battery survival, mast recommendation, ranking and
landing-error robustness. Writes visibility.npz, dates.npz, results.json (summary and ranking for every site) and
sites/<id>.json for every top site (scripts/site_report.py: skyline, hourly tracks, events, verdict).

Step 3, for every site, mast and hour (team PDF, Step 3; scripts/events.py):
  s = clamp((sun_el - H(sun_az) + r_sun) / (2 r_sun), 0, 1)     visible fraction of the Sun
  e = earth_el + r_earth > H(earth_az) + earth_margin           any part of Earth visible (NASA's rule); the
                                                                 margin models an antenna mask (default 0)
  b = (s > 0.5) and e                                           power and Earth contact together
  H is interpolated between neighbouring directions; r_sun and r_earth are that hour's disc radii (sky.npz).
Step 4, for a mission of --days starting at every hour of the sky file (the challenge asks for landing dates and
times). No weighted score: every number is a physical quantity.
  touchdown      more than half the Sun visible and Earth in view in the landing hour (power and a link at landing)
  survives       the battery (scripts/battery.py, sun-tracking array: an upper bound) never drops below e_min
  safe hour      touchdown, Earth in view for at least --min-dte-share of the mission (NASA: direct-with-Earth, no
                 relay), and survives. A landing day (UTC) is safe if any of its hours is; safe_landing_days counts
                 them ("launch delays ... alternative dates"), safe_landing_hours counts the hours
  f_sun, f_earth, f_both   share of hours with s > 0.5, with e, with b
  longest_dark_h longest run of hours without s > 0.5: the cold soak
  battery needed e_max - the lowest battery level of a mission (scripts/battery.py); per site and mast the most
                 that any safe landing hour needs
  best date      per site and mast: the best safe hour of each day, by the most hours of power and Earth together,
                 then the shortest darkness, then the earliest; the best days first. A mast with no safe date has none. sites/<id>.json shows the
                 recommended mast's best date (within 100 m when that check ran).
  recommended mast  the shortest mast with at least one safe landing date (information only)
  ranking        one list per mast (top_sites_by_mast, site ids): sites within 6 deg of the pole, slope under 10 deg,
                 every ray complete at that mast and at least one safe date; most safe landing days first, then
                 the least battery needed, then sites.csv order. The user picks the lander's mast (default 2 m).
  within 100 m   (--neighbours) a lander aimed at a site comes down anywhere within 100 m (NASA's landing accuracy),
                 so a date is safe for the site only if it is safe at every point there. Where that was checked, the
                 lists count those days instead, and a site with none leaves that mast's list;
                 recommended_mast_100m_m is the shortest mast with such a date. On the demo grid this matters: no
                 ranked site keeps a safe date within 100 m at 0 m.
Landing error (--neighbours): skylines at points within 100 m of the ranked sites (scripts/make_neighbours.py, then
scripts/run_horizon.py). Each point uses its parent's sky, since 100 m moves the Sun and Earth by only 0.003 deg.

Usage:
  python scripts/score_sites.py --horizon out/run --sky out/sky.npz --sites sites.csv --out out/results
  python scripts/make_neighbours.py sites.csv out/results/results.json --out out/nb/sites.csv
  python scripts/run_horizon.py data/ldem_75s_240m.lbl out/nb/sites.csv --fine data/ldem_80s_20m.lbl --out out/nb
  python scripts/score_sites.py --horizon out/run --sky out/sky.npz --sites sites.csv --neighbours out/nb --out out/results
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from numba import njit, prange

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.battery import Battery, simulate_windows  # noqa: E402
from scripts.events import earth_clearance, sun_clearance, sun_fraction  # noqa: E402
from scripts.site_report import site_report  # noqa: E402

GATE_LAT, GATE_SLOPE = -84.0, 10.0   # NASA's Artemis III reference: within 6 deg of the pole, slope under 10 deg
TRACK = ("sun_az", "sun_el", "earth_az", "earth_el")


def read_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


def load(horizon_dir, sky_path, sites_path):
    """Skylines, sky and sites, checked to describe the same sites in the same order."""
    h = Path(horizon_dir)
    meta = json.loads((h / "horizon_meta.json").read_text())
    H, D, ok = (np.load(h / f) for f in ("horizon.npy", "blocker.npy", "complete.npy"))
    sky = dict(np.load(sky_path))
    sites = read_csv(sites_path)
    lat, lon = sites["lat"].astype(float), sites["lon"].astype(float)
    if not (H.shape[0] == lat.size == sky["sun_az"].shape[0]):
        raise ValueError(f"site counts differ: horizon {H.shape[0]}, sites.csv {lat.size}, sky {sky['sun_az'].shape[0]}")
    if (np.abs(sky["site_lat"] - lat).max() > 1e-4 or np.abs((sky["site_lon"] - lon + 180) % 360 - 180).max() > 1e-4):
        raise ValueError("sky.npz and sites.csv list the sites in a different order")
    if "earth_radius_deg" not in sky:
        raise ValueError("sky.npz has no disc radii: re-run it with scripts/make_sky.py (v4)")
    if int(sky["step_hours"]) != 1 or not str(sky["time_utc"][0]).endswith("T00:00:00"):
        raise ValueError("Step 4 needs an hourly sky file starting at 00:00 UTC")
    return meta, H, D, ok, sky, sites


def visibility(H, sky, earth_margin):
    """s float32, e bool, b bool, each [sites, masts, hours]."""
    shape = (H.shape[0], H.shape[1], sky["sun_az"].shape[1])
    s, e = np.empty(shape, np.float32), np.empty(shape, bool)
    for m in range(H.shape[1]):
        s[:, m] = sun_fraction(sun_clearance(H[:, m], sky["sun_az"], sky["sun_el"]), sky["sun_radius_deg"][None, :])
        e[:, m] = earth_clearance(H[:, m], sky["earth_az"], sky["earth_el"], sky["earth_radius_deg"][None, :],
                                  earth_margin) > 0
    return s, e, (s > 0.5) & e


def window_sum(flags, hours):
    """flags [..., T] -> True hours in the mission of `hours` starting at every hour, [..., T - hours + 1] (int16)."""
    c = np.cumsum(flags, axis=-1, dtype=np.int32)
    c = np.concatenate([np.zeros(c.shape[:-1] + (1,), np.int32), c], axis=-1)
    return (c[..., hours:] - c[..., :-hours]).astype(np.int16)


@njit(parallel=True, cache=True)
def window_longest_run(flags, hours):
    """flags [sites, T] -> longest run of True inside the mission of `hours` starting at every hour (int16)."""
    n, starts = flags.shape[0], flags.shape[1] - hours + 1
    out = np.empty((n, starts), np.int16)
    for i in prange(n):
        for k in range(starts):
            run = best = 0
            for h in range(k, k + hours):
                run = run + 1 if flags[i, h] else 0
                best = max(best, run)
            out[i, k] = best
    return out


def date_metrics(s, e, b, hours, battery, min_dte_share):
    """Every metric for every site, mast and landing hour (a mission starting at every hour of the sky file):
    dict of arrays [sites, masts, starts]."""
    starts = s.shape[-1] - hours + 1
    shape = s.shape[:2] + (starts,)
    met = {k: np.empty(shape, t) for k, t in (("n_sun", np.int16), ("n_earth", np.int16), ("n_both", np.int16),
                                              ("gap_h", np.int16), ("lowest_Wh", np.float32), ("death_h", np.int16),
                                              ("touchdown", bool))}
    for m in range(s.shape[1]):
        lit = s[:, m] > 0.5
        met["n_sun"][:, m], met["n_earth"][:, m] = window_sum(lit, hours), window_sum(e[:, m], hours)
        met["n_both"][:, m], met["gap_h"][:, m] = window_sum(b[:, m], hours), window_longest_run(~lit, hours)
        met["lowest_Wh"][:, m], met["death_h"][:, m] = simulate_windows(s[:, m], hours, battery)
        met["touchdown"][:, m] = b[:, m, :starts]
    met["safe"] = met["touchdown"] & (met["n_earth"] >= min_dte_share * hours) & (met["death_h"] < 0)
    return met


def by_day(a, fill):
    """[..., starts] (hourly, the sky file starts at 00:00 UTC) -> [..., days, 24], the last day padded with fill."""
    pad = (-a.shape[-1]) % 24
    a = np.concatenate([a, np.full(a.shape[:-1] + (pad,), fill, a.dtype)], axis=-1)
    return a.reshape(a.shape[:-1] + (-1, 24))


def safe_days(safe):
    """Landing days (UTC) with at least one safe landing hour, [...]."""
    return by_day(safe, False).any(-1).sum(-1)


def best_dates(met, hours, top_n):
    """Start indices [top_n, sites, masts] of the best landing hour on each of the best days: safe hours first, most
    hours of power and Earth together, then the shortest darkness, then the earliest. Entries past a site's safe
    days are not safe (check met['safe'])."""
    key = np.where(met["safe"], met["n_both"].astype(np.int32) * (hours + 1) + (hours - met["gap_h"]), -1)
    day = by_day(key, -1)                                       # [..., days, 24]
    days = np.argsort(-day.max(-1), axis=-1, kind="stable")[..., :top_n]
    hour = np.take_along_axis(day.argmax(-1), days, axis=-1)    # argmax: the earliest of equal hours
    return (days * 24 + hour).transpose(2, 0, 1)


def recommended_mast(n_safe, masts):
    """Shortest mast with at least one safe landing date; NaN if none."""
    has = n_safe > 0
    return np.where(has.any(axis=1), np.asarray(masts)[has.argmax(axis=1)], np.nan)


def battery_needed(met, e_max):
    """The most battery energy (Wh) any safe landing hour draws, e_max - lowest level, [sites, masts]; NaN if none."""
    need = np.where(met["safe"], e_max - met["lowest_Wh"], -np.inf).max(-1)
    return np.where(np.isfinite(need), need, np.nan)


def ranking(rows, days, need_Wh):
    """Site rows ordered by days (more first), then battery needed (less first), then sites.csv order."""
    rows = np.asarray(rows, int)
    return rows[np.lexsort((rows, need_Wh[rows], -days[rows]))].tolist()


def neighbour_safe(nb_dir, sky, hours, battery, earth_margin, min_dte_share, parent_of, parent_safe):
    """Landing dates safe at the parent and at every point within 100 m [sites, masts, dates] (False for sites not
    checked), whether every point's rays are complete [sites, masts], and the points per site."""
    H_nb, ok_nb = np.load(Path(nb_dir) / "horizon.npy"), np.load(Path(nb_dir) / "complete.npy")
    nb_sky = {k: (v[parent_of] if k in TRACK else v) for k, v in sky.items()}
    safe = date_metrics(*visibility(H_nb, nb_sky, earth_margin), hours, battery, min_dte_share)["safe"]
    safe_100m = np.zeros_like(parent_safe)
    complete = np.zeros(parent_safe.shape[:2], bool)
    for p in np.unique(parent_of):
        rows = parent_of == p
        safe_100m[p] = parent_safe[p] & safe[rows].all(axis=0)
        complete[p] = ok_nb[rows].all(axis=(0, 2))
    return safe_100m, complete, np.bincount(parent_of, minlength=parent_safe.shape[0])


def r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", required=True, help="Step 1 folder (horizon.npy, blocker.npy, complete.npy, meta)")
    ap.add_argument("--sky", required=True, help="Step 2 sky.npz (hourly, from scripts/make_sky.py)")
    ap.add_argument("--sites", required=True, help="the sites.csv both steps used")
    ap.add_argument("--neighbours", help="Step 1 folder for the points within 100 m of the ranked sites")
    ap.add_argument("--out", default="out/results")
    ap.add_argument("--days", type=int, default=14, help="mission length")
    ap.add_argument("--min-dte-share", type=float, default=0.5,
                    help="share of mission hours Earth must be in view for a safe date (no relay)")
    ap.add_argument("--earth-margin", type=float, default=0.0,
                    help="degrees Earth must clear the skyline by (antenna mask); 0 = NASA's any-part-visible rule")
    ap.add_argument("--top", type=int, default=20, help="sites ranked per mast, with a sites/<id>.json each")
    ap.add_argument("--dates", type=int, default=3, help="best landing dates listed per site and mast")
    for name, default in vars(Battery()).items():
        ap.add_argument(f"--{name.replace('_', '-')}", type=float, default=default, help=f"battery {name}")
    a = ap.parse_args()

    meta, H, D, ok, sky, sites = load(a.horizon, a.sky, a.sites)
    battery = Battery(a.e_max, a.e_min, a.p_panel, a.p_load, a.dt)
    masts, hours, n_sites = [float(m) for m in meta["masts_m"]], a.days * 24, H.shape[0]
    ids = sites["id"].astype(str)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    s, e, b = visibility(H, sky, a.earth_margin)
    np.savez_compressed(out / "visibility.npz", s=s, e=e, b=b, time_utc=sky["time_utc"], masts_m=np.array(masts))
    met = date_metrics(s, e, b, hours, battery, a.min_dte_share)
    n_safe = safe_days(met["safe"])                             # [sites, masts]
    n_safe_h = met["safe"].sum(-1)
    starts = sky["time_utc"][: s.shape[-1] - hours + 1]         # every landing hour
    order = best_dates(met, hours, a.dates)                     # [dates, sites, masts]
    at_best = {k: np.take_along_axis(v, order[0][..., None], axis=-1)[..., 0] for k, v in met.items()}
    need_Wh = battery_needed(met, battery.e_max)               # [sites, masts], worst safe landing hour
    survived_h = np.where(met["death_h"] < 0, hours, met["death_h"]).max(axis=-1)   # longest any date lasts
    rec = recommended_mast(n_safe, masts)
    np.savez_compressed(out / "dates.npz", start_utc=starts, safe=met["safe"], touchdown=met["touchdown"],
                        survives=met["death_h"] < 0, masts_m=np.array(masts))

    lat, lon, slope = (sites[k].astype(float) for k in ("lat", "lon", "slope"))
    passes_gates = (lat <= GATE_LAT) & (slope < GATE_SLOPE)
    complete = ok.all(axis=2)                                   # [sites, masts]
    candidates = [np.flatnonzero(passes_gates & complete[:, m] & (n_safe[:, m] > 0)) for m in range(len(masts))]
    by_mast = [ranking(c, n_safe[:, m], need_Wh[:, m])[: a.top] for m, c in enumerate(candidates)]

    days_100m = np.full((n_sites, len(masts)), np.nan)
    complete_100m = np.zeros((n_sites, len(masts)), bool)
    n_points = np.zeros(n_sites, int)
    rec_100m = np.full(n_sites, np.nan)
    order_100m = safe_100m = None
    if a.neighbours:
        nb = read_csv(Path(a.neighbours) / "sites.csv")
        parent_of = nb["parent"].astype(int)
        missing = {i for rows in by_mast for i in rows} - set(parent_of.tolist())
        if missing:
            raise ValueError(f"--neighbours does not cover ranked sites {sorted(ids[list(missing)])[:10]}: "
                             "re-run scripts/make_neighbours.py on this results.json")
        safe_100m, complete_100m, n_points = neighbour_safe(a.neighbours, sky, hours, battery, a.earth_margin,
                                                            a.min_dte_share, parent_of, met["safe"])
        checked = n_points > 0
        days_100m = np.where(checked[:, None], safe_days(safe_100m), np.nan)
        order_100m = best_dates(met | {"safe": safe_100m}, hours, a.dates)
        rec_100m = np.where(checked, recommended_mast(np.nan_to_num(days_100m), masts), np.nan)
        key = np.where(checked[:, None], np.nan_to_num(days_100m), n_safe)
        # a site whose dates all fail somewhere within 100 m is not safe to aim at, so it leaves that mast's list
        candidates = [c[key[c, m] > 0] for m, c in enumerate(candidates)]
        by_mast = [ranking(c, key[:, m], need_Wh[:, m])[: a.top] for m, c in enumerate(candidates)]
    ranked = sorted({i for rows in by_mast for i in rows})

    results = {
        "meta": {
            "version": 4, "sky_source": str(sky["script_version"]) + " (NASA SPICE, DE421)",
            "span": {"first_start": str(starts[0])[:13], "last_start": str(starts[-1])[:13],
                     "n_days": -(-len(starts) // 24), "n_hours": len(starts)},
            "mission_days": a.days, "masts_m": masts, "default_mast_m": 2.0, "n_az": int(meta["n_az"]),
            "min_dte_share": a.min_dte_share, "earth_margin_deg": a.earth_margin,
            "gates": {"lat_max_deg": GATE_LAT, "slope_max_deg": GATE_SLOPE}, "landing_error_m": 100,
            "lander": battery.profile(),
            "definitions": {
                "safe_landing_date": f"a day with at least one safe landing hour: touchdown with more than half the "
                                     f"Sun and Earth in view, Earth in view for at least {a.min_dte_share:.0%} of the "
                                     f"{a.days}-day mission (no relay), and the battery never below {battery.e_min:g} Wh",
                "ranking": "one list per mast height: most safe landing days (safe at every point within 100 m "
                           "where that was checked; sites with none there are left out), then the least battery "
                           "needed",
                "battery_needed_Wh": "the most battery energy any safe landing hour draws: a full charge minus the "
                                     "lowest level during the mission (the battery model, so sunlight that comes back "
                                     f"partway counts); at most {battery.e_max - battery.e_min:g} Wh by the safe rule",
                "default_mast": "2 m: the best-fit observer height when the engine is checked against NASA's maps",
                "recommended_mast_m": "the shortest mast with at least one safe landing date (information only)",
                "fields": "per-mast numbers are for that mast's best landing date (best_dates[0]); null if it has "
                          "none"},
            "top_sites_by_mast": {str(mast): ids[rows].tolist() for mast, rows in zip(masts, by_mast)}},
        "sites": []}
    for i in range(n_sites):
        site = {"id": ids[i], "lat": r(lat[i], 5), "lon": r(lon[i], 4),
                "x_m": r(float(sites["x"][i]), 1), "y_m": r(float(sites["y"][i]), 1), "slope_deg": r(slope[i], 1),
                "passes_gates": bool(passes_gates[i]), "recommended_mast_m": r(rec[i], 1),
                "recommended_mast_100m_m": r(rec_100m[i], 1), "landing_error_points": int(n_points[i]),
                "detail_file": f"sites/{ids[i]}.json" if i in ranked else None, "masts": {}}
        for m, mast in enumerate(masts):
            best = n_safe[i, m] > 0
            pick = lambda k, f=lambda v: v: f(at_best[k][i, m]) if best else None
            site["masts"][str(mast)] = {
                "safe_landing_days": int(n_safe[i, m]), "safe_landing_hours": int(n_safe_h[i, m]),
                "safe_days_within_100m": None if not n_points[i] else int(days_100m[i, m]),
                "best_dates": [{"start": str(starts[order[j, i, m]])[:13],
                                "f_both": r(met["n_both"][i, m, order[j, i, m]] / hours),
                                "longest_dark_h": int(met["gap_h"][i, m, order[j, i, m]])}
                               for j in range(order.shape[0]) if met["safe"][i, m, order[j, i, m]]],
                "f_sun": pick("n_sun", lambda v: r(v / hours)), "f_earth": pick("n_earth", lambda v: r(v / hours)),
                "f_both": pick("n_both", lambda v: r(v / hours)), "longest_dark_h": pick("gap_h", int),
                "battery_needed_Wh": r(need_Wh[i, m], 1) if best else None,
                "battery_lowest_Wh": pick("lowest_Wh", lambda v: r(v, 1)),
                "longest_survival_h": int(survived_h[i, m]), "complete": bool(complete[i, m]),
                "best_dates_within_100m": None if not n_points[i] else
                    [str(starts[order_100m[j, i, m]])[:13] for j in range(order_100m.shape[0])
                     if safe_100m[i, m, order_100m[j, i, m]]],
                "complete_within_100m": None if not n_points[i] else bool(complete_100m[i, m])}
        results["sites"].append(site)
    (out / "results.json").write_text(json.dumps(results))

    detail = out / "sites"
    detail.mkdir(exist_ok=True)
    for i in ranked:                                   # at the 100 m mast and date when that check found one
        use_100m = np.isfinite(rec_100m[i])
        m = masts.index(rec_100m[i] if use_100m else rec[i])
        k = int((order_100m if use_100m else order)[0, i, m])
        track = {key: sky[key][i, k: k + hours] for key in TRACK}
        track |= {key: sky[key][k: k + hours] for key in ("time_utc", "sun_radius_deg", "earth_radius_deg")}
        info = {key: results["sites"][i][key] for key in ("id", "lat", "lon", "x_m", "y_m", "slope_deg")}
        report = site_report(info, H[i, m], D[i, m], ok[i, m], track, masts[m], battery, a.earth_margin)
        (detail / f"{info['id']}.json").write_text(json.dumps(report))

    print(f"{n_sites} sites x {len(masts)} masts x {len(starts)} landing hours ({a.days}-day missions) -> {out}")
    print(f"safe date: touchdown in Sun and Earth, Earth in view >= {a.min_dte_share:.0%} of the mission, battery "
          f"bridges {battery.bridge_hours():.1f} h (sun-tracking array: an upper bound)")
    print(f"pass the gates: {passes_gates.sum()} | rays all complete: {complete.all(axis=1).sum()}")
    for m, mast in enumerate(masts):
        head = ", ".join(f"{ids[i]} ({n_safe[i, m]}" + (f", {days_100m[i, m]:.0f} within 100 m" if n_points[i] else "")
                         + ")" for i in by_mast[m][:3])
        print(f"  mast {mast:>4} m: {(n_safe[:, m] > 0).sum()} of {n_sites} sites have a safe landing date; top: {head}")


if __name__ == "__main__":
    main()
