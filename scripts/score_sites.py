"""Steps 3-4 (CE 3): visibility, scores, battery survival, best landing dates, mast recommendation and landing-error
robustness, written as visibility.npz, dates.npz and results.json (the web app's input).

Step 3, for every site, mast and hour (team PDF, Step 3):
  s = clamp((sun_el - H(sun_az) + r_sun) / (2 r_sun), 0, 1)     visible fraction of the Sun
  e = earth_el + r_earth > H(earth_az)                          any part of Earth visible (NASA's rule)
  b = (s > 0.5) and e                                           power and Earth contact together
  H is interpolated between neighbouring directions; r_sun and r_earth are that hour's disc radii (sky.npz).
Step 4, for a mission of --days starting at 00:00 UTC on every day of the sky file:
  f_sun, f_earth, f_both = share of hours with s > 0.5, with e, with b; gap = longest run of hours without s > 0.5
  score = w_sun f_sun + w_earth f_earth + w_both f_both - w_gap gap / mission hours
  battery (scripts/battery.py): the lander starts full and survives if it never drops below e_min
  best date (per site and mast): the highest score among dates it survives, or the highest score if it never does.
    Every number results.json gives for a site and mast is for that date.
  recommended mast: the shortest mast whose best score is within --good-enough of the best mast's
  ranked sites: within 6 deg of the pole, slope under 10 deg, every ray complete, and surviving at some mast;
    ordered by best score, or, with --neighbours, by the worst score within 100 m at the recommended mast
Landing error (--neighbours): skylines at points within 100 m of the top sites (scripts/make_neighbours.py, then
scripts/run_horizon.py). Each point uses its parent's sky, since 100 m moves the Sun and Earth by only 0.003 deg.
worst_score_100m is the lowest score among those points, for the parent's best date at that mast.

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
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.battery import Battery, levels, simulate  # noqa: E402

GATE_LAT, GATE_SLOPE = -84.0, 10.0   # NASA's Artemis III reference: within 6 deg of the pole, slope under 10 deg


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


def skyline_at(H, az):
    """H [sites, n_az] interpolated between neighbouring directions at az [sites, hours] (degrees)."""
    n_az = H.shape[1]
    pos = (az % 360) * (n_az / 360)
    j0 = np.floor(pos).astype(int) % n_az
    frac = pos - np.floor(pos)
    h0 = np.take_along_axis(H, j0, axis=1)
    h1 = np.take_along_axis(H, (j0 + 1) % n_az, axis=1)
    return h0 * (1 - frac) + h1 * frac


def visibility(H, sky):
    """s float32, e bool, b bool, each [sites, masts, hours]."""
    r_sun, r_earth = sky["sun_radius_deg"][None, :], sky["earth_radius_deg"][None, :]
    shape = (H.shape[0], H.shape[1], sky["sun_az"].shape[1])
    s, e = np.empty(shape, np.float32), np.empty(shape, bool)
    for m in range(H.shape[1]):
        s[:, m] = np.clip((sky["sun_el"] - skyline_at(H[:, m], sky["sun_az"]) + r_sun) / (2 * r_sun), 0, 1)
        e[:, m] = sky["earth_el"] + r_earth > skyline_at(H[:, m], sky["earth_az"])
    return s, e, (s > 0.5) & e


def windows(a, hours):
    """Views [..., dates, hours] of a [..., all hours]: one mission window starting at 00:00 on every day."""
    return sliding_window_view(a, hours, axis=-1)[..., ::24, :]


def longest_run(flags):
    """Longest run of True along the last axis."""
    run = np.zeros(flags.shape[:-1], np.int32)
    best = run.copy()
    for h in range(flags.shape[-1]):
        run = np.where(flags[..., h], run + 1, 0)
        best = np.maximum(best, run)
    return best


def date_metrics(s, e, b, hours, weights, battery):
    """Every metric for every site, mast and landing date: dict of arrays [sites, masts, dates]."""
    out = {k: [] for k in ("f_sun", "f_earth", "f_both", "gap_h", "score", "lowest_Wh", "death_h")}
    for m in range(s.shape[1]):
        sw, ew, bw = windows(s[:, m], hours), windows(e[:, m], hours), windows(b[:, m], hours)
        lit = sw > 0.5
        f_sun, f_earth, f_both = lit.mean(-1), ew.mean(-1), bw.mean(-1)
        gap = longest_run(~lit)
        w = weights
        score = w["sun"] * f_sun + w["earth"] * f_earth + w["both"] * f_both - w["gap"] * gap / hours
        lowest, death = simulate(sw, battery)
        for k, v in zip(out, (f_sun, f_earth, f_both, gap, score, lowest, death)):
            out[k].append(v)
    return {k: np.stack(v, axis=1) for k, v in out.items()}


def best_dates(score, survives, top_n):
    """Indices [top_n, sites, masts] of the best dates: surviving dates first, then by score."""
    key = np.where(survives, score, score - 1e6)      # any surviving date beats every failing one
    return np.argsort(-key, axis=-1)[..., :top_n].transpose(2, 0, 1)


def recommended_mast(best_score, best_survives, masts, good_enough):
    """Shortest mast within good_enough of the best mast's best score, among masts that survive; NaN if none."""
    rec = np.full(best_score.shape[0], np.nan)
    for i in range(best_score.shape[0]):
        ok = best_survives[i]
        if ok.any():
            target = best_score[i, ok].max() - good_enough
            rec[i] = next(m for m, sc, k in zip(masts, best_score[i], ok) if k and sc >= target)
    return rec


def neighbour_worst(nb_dir, sky, metric_args, parent_of, best_k, n_sites):
    """Worst score and all-survive over each parent's points within 100 m, at the parent's best date per mast."""
    H_nb, ok_nb = np.load(Path(nb_dir) / "horizon.npy"), np.load(Path(nb_dir) / "complete.npy")
    nb_sky = {k: (v[parent_of] if k in ("sun_az", "sun_el", "earth_az", "earth_el") else v) for k, v in sky.items()}
    s, e, b = visibility(H_nb, nb_sky)
    met = date_metrics(s, e, b, *metric_args)
    k = best_k[parent_of]                                   # [points, masts]: the parent's best date
    pick = lambda a: np.take_along_axis(a, k[..., None], axis=-1)[..., 0]
    score, survives = pick(met["score"]), pick(met["death_h"]) < 0
    worst = np.full((n_sites, H_nb.shape[1]), np.nan)
    all_ok = np.zeros((n_sites, H_nb.shape[1]), bool)
    for p in np.unique(parent_of):
        rows = parent_of == p
        worst[p] = score[rows].min(axis=0)
        all_ok[p] = survives[rows].all(axis=0) & ok_nb[rows].all(axis=(0, 2))
    return worst, all_ok, np.bincount(parent_of, minlength=n_sites)


def r(x, n=3):
    return None if x is None or not np.isfinite(x) else round(float(x), n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", required=True, help="Step 1 folder (horizon.npy, blocker.npy, complete.npy, meta)")
    ap.add_argument("--sky", required=True, help="Step 2 sky.npz (hourly, from scripts/make_sky.py)")
    ap.add_argument("--sites", required=True, help="the sites.csv both steps used")
    ap.add_argument("--neighbours", help="Step 1 folder for the points within 100 m of the top sites")
    ap.add_argument("--out", default="out/results")
    ap.add_argument("--days", type=int, default=14, help="mission length")
    ap.add_argument("--weights", type=float, nargs=4, default=[0.30, 0.20, 0.35, 0.15],
                    metavar=("SUN", "EARTH", "BOTH", "GAP"))
    ap.add_argument("--good-enough", type=float, default=0.05, help="mast recommendation tolerance on the score")
    ap.add_argument("--top", type=int, default=20, help="sites with hour-by-hour timelines")
    ap.add_argument("--dates", type=int, default=3, help="best landing dates listed per site and mast")
    for name, default in vars(Battery()).items():
        ap.add_argument(f"--{name.replace('_', '-')}", type=float, default=default, help=f"battery {name}")
    a = ap.parse_args()

    meta, H, D, ok, sky, sites = load(a.horizon, a.sky, a.sites)
    battery = Battery(a.e_max, a.e_min, a.p_panel, a.p_load, a.dt)
    weights = dict(zip(("sun", "earth", "both", "gap"), a.weights))
    masts, hours, n_sites = [float(m) for m in meta["masts_m"]], a.days * 24, H.shape[0]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    s, e, b = visibility(H, sky)
    np.savez_compressed(out / "visibility.npz", s=s, e=e, b=b, time_utc=sky["time_utc"], masts_m=np.array(masts))
    met = date_metrics(s, e, b, hours, weights, battery)
    survives = met["death_h"] < 0
    starts = sky["time_utc"][: s.shape[-1] - hours + 1 : 24]
    best_k = best_dates(met["score"], survives, a.dates)      # [dates, sites, masts]
    at_best = {k: np.take_along_axis(v, best_k[0][..., None], axis=-1)[..., 0] for k, v in met.items()}
    best_survives = at_best["death_h"] < 0
    rec = recommended_mast(at_best["score"], best_survives, masts, a.good_enough)
    np.savez_compressed(out / "dates.npz", start_utc=starts, score=met["score"].astype(np.float32),
                        survives=survives, masts_m=np.array(masts))

    lat, slope = sites["lat"].astype(float), sites["slope"].astype(float)
    passes_gates = (lat <= GATE_LAT) & (slope < GATE_SLOPE)
    complete = ok.all(axis=2)                                  # [sites, masts]
    rankable = passes_gates & complete.all(axis=1) & best_survives.any(axis=1)
    overall = np.where(rankable, np.where(best_survives, at_best["score"], -np.inf).max(axis=1), -np.inf)
    top = [int(i) for i in np.argsort(-overall)[: a.top] if np.isfinite(overall[i])]

    worst = np.full((n_sites, len(masts)), np.nan)
    all_ok = np.zeros((n_sites, len(masts)), bool)
    n_points = np.zeros(n_sites, int)
    if a.neighbours:
        nb = read_csv(Path(a.neighbours) / "sites.csv")
        parent_of = nb["parent"].astype(int)
        worst, all_ok, n_points = neighbour_worst(a.neighbours, sky, (hours, weights, battery), parent_of,
                                                  best_k[0], n_sites)
        if not set(top) <= set(parent_of.tolist()):
            raise ValueError("--neighbours does not cover every top site: re-run scripts/make_neighbours.py")
        robust = lambda i: worst[i, masts.index(rec[i])]
        top.sort(key=lambda i: (-robust(i), -overall[i]))    # rank by the worst score within 100 m

    results = {
        "meta": {
            "version": 2, "sky_source": str(sky["script_version"]) + " (NASA SPICE, DE421)",
            "battery": vars(battery) | {"bridge_hours": battery.bridge_hours(),
                                        "sources": "IoT: p_panel Nova-C 200 W (Wikipedia); e_max 25 Ah x 28 V; "
                                                   "p_load ESTIMATE from Odysseus; e_min ASSUMPTION 20%"},
            "mission_days": a.days, "weights": weights, "masts_m": masts, "n_az": int(meta["n_az"]),
            "gates": {"lat_max_deg": GATE_LAT, "slope_max_deg": GATE_SLOPE},
            "landing_error_m": 100, "first_start": str(starts[0]), "last_start": str(starts[-1]),
            "fields": "every per-mast number is for that site and mast's best landing date (best_dates[0])",
            "f_sun": "share of mission hours with more than half the Sun visible",
            "top_sites": top},
        "sites": []}
    for i in range(n_sites):
        site = {"id": str(sites["id"][i]), "lat": r(lat[i], 5), "lon": r(float(sites["lon"][i]), 4),
                "x_m": r(float(sites["x"][i]), 1), "y_m": r(float(sites["y"][i]), 1), "slope_deg": r(slope[i], 1),
                "passes_gates": bool(passes_gates[i]), "recommended_mast_m": r(rec[i], 1),
                "landing_error_points": int(n_points[i]), "masts": {}}
        for m, mast in enumerate(masts):
            site["masts"][str(mast)] = {
                "best_dates": [{"start": str(starts[best_k[j, i, m]])[:13], "score": r(met["score"][i, m, best_k[j, i, m]])}
                               for j in range(best_k.shape[0])],
                "score": r(at_best["score"][i, m]), "f_sun": r(at_best["f_sun"][i, m]),
                "f_earth": r(at_best["f_earth"][i, m]), "f_both": r(at_best["f_both"][i, m]),
                "longest_dark_h": int(at_best["gap_h"][i, m]), "survives": bool(best_survives[i, m]),
                "battery_lowest_Wh": r(at_best["lowest_Wh"][i, m], 1),
                "dies_at_hour": None if best_survives[i, m] else int(at_best["death_h"][i, m]),
                "survivable_dates": int(survives[i, m].sum()), "complete": bool(complete[i, m]),
                "worst_score_100m": r(worst[i, m]), "survives_within_100m": bool(all_ok[i, m]) if n_points[i] else None}
        if i in top:
            m = masts.index(rec[i])
            i0 = int(best_k[0, i, m]) * 24
            hrs = slice(i0, i0 + hours)
            site["timeline"] = {
                "mast_m": masts[m], "start": str(starts[best_k[0, i, m]])[:13], "hours": hours,
                "sun_fraction": [r(x, 2) for x in s[i, m, hrs]], "earth_visible": [bool(x) for x in e[i, m, hrs]],
                "both": [bool(x) for x in b[i, m, hrs]], "battery_Wh": [r(x, 1) for x in levels(s[i, m, hrs], battery)],
                **{k: [r(x, 2) for x in sky[k][i, hrs]] for k in ("sun_az", "sun_el", "earth_az", "earth_el")}}
            step = H.shape[2] // 360
            site["skyline_deg"] = {str(mast): [r(x, 2) for x in H[i, mm, ::step]] for mm, mast in enumerate(masts)}
            site["blocker_km"] = {str(mast): [r(x / 1e3, 2) for x in D[i, mm, ::step]] for mm, mast in enumerate(masts)}
        results["sites"].append(site)
    (out / "results.json").write_text(json.dumps(results))

    print(f"{n_sites} sites x {len(masts)} masts x {len(starts)} landing dates ({a.days}-day missions) -> {out}")
    print(f"battery bridges {battery.bridge_hours():.1f} h without sunlight")
    for m, mast in enumerate(masts):
        print(f"  mast {mast:>4} m: survives on at least one date at {best_survives[:, m].sum()} of {n_sites} sites")
    print(f"pass the gates: {passes_gates.sum()} | rays all complete: {complete.all(axis=1).sum()} | ranked: {rankable.sum()}")
    print(f"top {len(top)}: {top[:10]}{' ...' if len(top) > 10 else ''}")
    if a.neighbours:
        print(f"landing error: {n_points.astype(bool).sum()} sites checked with up to {n_points.max()} points each")


if __name__ == "__main__":
    main()
