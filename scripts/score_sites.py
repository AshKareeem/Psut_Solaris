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
  best date      per site and mast: the best safe hour of each day: a firm touchdown first (the Sun's centre and
                 Earth's top both at least 0.5 deg above the skyline, so not marginal), then the most hours of power
                 and Earth together, then the shortest darkness, then the earliest; the best days first. A mast with no safe date has none. sites/<id>.json shows the
                 recommended mast's best date (within 100 m when that check ran).
  recommended mast  the shortest mast with at least one safe landing date (information only)
  ranking        one list per mast (top_sites_by_mast, site ids): sites within 6 deg of the pole, slope under 10 deg,
                 every ray complete at that mast and at least one safe date; most safe landing days first, then
                 the most safe days on the site's own point (differs only within 100 m), then the least battery
                 needed, then sites.csv order. The user picks the lander's mast (default 2 m).
  within 100 m   (--neighbours) a lander aimed at a site comes down anywhere within 100 m (NASA's landing accuracy),
                 so a date is safe for the site only if it is safe at every point there, and only if every point
                 also has ground under 10 deg over 100 m (council R3, option A: NASA's slope gate and its 100 m
                 landing accuracy together; each point's slope comes from make_neighbours.py). The lists then hold only
                 checked sites (the first pass's lists, all checked by make_neighbours.py) and count those days; a
                 site safe on its point but nowhere within 100 m stays, ranked below (0 days within 100 m).
                 recommended_mast_100m_m is the shortest mast with such a date.
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
import shutil
import sys
from pathlib import Path

import numpy as np
from numba import njit, prange

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.battery import Battery, simulate_windows  # noqa: E402
from scripts.events import earth_clearance, sun_clearance, sun_fraction  # noqa: E402
from scripts.site_report import MARGINAL_DEG, PROVENANCE, bearing, site_report  # noqa: E402

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


def firm_touchdown(H, sky, earth_margin):
    """[sites, masts, hours] bool: the Sun's centre and the top of Earth's disc both clear the skyline by at least
    MARGINAL_DEG, so a landing that hour is not marginal (scripts/site_report.py flags the others)."""
    out = np.empty((H.shape[0], H.shape[1], sky["sun_az"].shape[1]), bool)
    for m in range(H.shape[1]):
        out[:, m] = ((sun_clearance(H[:, m], sky["sun_az"], sky["sun_el"]) >= MARGINAL_DEG)
                     & (earth_clearance(H[:, m], sky["earth_az"], sky["earth_el"], sky["earth_radius_deg"][None, :],
                                        earth_margin) >= MARGINAL_DEG))
    return out


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


def best_dates(met, firm, hours, top_n):
    """Start indices [top_n, sites, masts] of the best landing hour on each of the best days: safe hours first, a firm
    touchdown (firm [sites, masts, starts], firm_touchdown) first, then the most hours of power and Earth together,
    then the shortest darkness, then the earliest. Entries past a site's safe days are not safe (check met['safe'])."""
    key = np.where(met["safe"], firm.astype(np.int32) * (hours + 1) ** 2
                   + met["n_both"].astype(np.int32) * (hours + 1) + (hours - met["gap_h"]), -1)
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


def ranking(rows, days, on_target, need_Wh):
    """Site rows ordered by days (more first; safe within 100 m when checked), then safe days on the site's own
    point (more first), then battery needed (less first), then sites.csv order."""
    rows = np.asarray(rows, int)
    return rows[np.lexsort((rows, need_Wh[rows], -on_target[rows], -days[rows]))].tolist()


def ranking_keys(checked_100m):
    """The ranking's keys in order, as (field in results.json masts{}, plain words, 'more' or 'less' is better).
    Without the 100 m check the first key is the exact point's days, so the second adds nothing and is left out."""
    keys = [("safe_days_within_100m", "safe landing days if the lander misses by up to 100 m", "more"),
            ("safe_landing_days", "safe landing days on the exact point", "more"),
            ("battery_needed_Wh", "battery needed (worst safe landing)", "less")]
    return keys if checked_100m else keys[1:]


def rank_reasons(rows, values, ids, keys):
    """For an ordered list of site rows: {row: sentence} saying which key puts it ahead of the next site and behind
    the one before, with both numbers. values[field][row] holds each key's number (NaN: none)."""
    def show(field, row):
        v = values[field][row]
        return "none" if not np.isfinite(v) else f"{v:.0f} Wh" if field == "battery_needed_Wh" else f"{v:.0f}"

    def decider(a, b):                      # first key on which rows a and b differ
        for field, words, _ in keys:
            va, vb = values[field][a], values[field][b]
            if not (va == vb or (np.isnan(va) and np.isnan(vb))):
                return f"{words}: {show(field, a)} vs {show(field, b)}"
        return "every metric ties; listed by site order"

    out = {}
    for k, row in enumerate(rows):
        parts = [f"#{k + 1} of {len(rows)}."]
        if k + 1 < len(rows):
            parts.append(f"Ahead of #{k + 2} (site {ids[rows[k + 1]]}): {decider(row, rows[k + 1])}.")
        if k > 0:
            parts.append(f"Behind #{k} (site {ids[rows[k - 1]]}): {decider(rows[k - 1], row)}.")
        out[row] = " ".join(parts)
    return out


def neighbour_safe(nb_dir, sky, hours, battery, earth_margin, min_dte_share, parent_of, parent_safe, steep,
                   details=False):
    """Landing dates safe at the parent and at every point within 100 m [sites, masts, dates] (False for sites not
    checked), whether every point's rays are complete [sites, masts], and the points per site. steep [points]: the
    point's slope over 100 m is at or above the gate, so no date is safe there. With details, also the per-point
    metrics it already computes ({"met": date_metrics dict with steep applied to "safe", "s", "e"}), for the risk
    block's miss table; the default return is unchanged."""
    H_nb, ok_nb = np.load(Path(nb_dir) / "horizon.npy"), np.load(Path(nb_dir) / "complete.npy")
    nb_sky = {k: (v[parent_of] if k in TRACK else v) for k, v in sky.items()}
    s_nb, e_nb, b_nb = visibility(H_nb, nb_sky, earth_margin)
    met_nb = date_metrics(s_nb, e_nb, b_nb, hours, battery, min_dte_share)
    safe = met_nb["safe"]
    safe[steep] = False
    safe_100m = np.zeros_like(parent_safe)
    complete = np.zeros(parent_safe.shape[:2], bool)
    for p in np.unique(parent_of):
        rows = parent_of == p
        safe_100m[p] = parent_safe[p] & safe[rows].all(axis=0)
        complete[p] = ok_nb[rows].all(axis=(0, 2))
    counts = np.bincount(parent_of, minlength=parent_safe.shape[0])
    if details:
        return safe_100m, complete, counts, {"met": met_nb, "s": s_nb, "e": e_nb}
    return safe_100m, complete, counts


# ---------------------------------------------------------------------------------------------------------------
# The risk block (failsafe spec, commit 1): launch delays and a 100 m miss, for the mission files this script
# writes. Every flag is read from the arrays above (date_metrics, neighbour_safe); nothing is recomputed.
DELAY_SLIPS_H = (1, 6, 24, 709)              # 709 h: the one-lunation slip, a labelled assumption of the spec
LUNATION_LABEL = "one lunation (29.53 days)"


def consecutive_safe(safe, k):
    """Consecutive safe landing hours in safe [starts] from hour k on: 1 = only hour k itself is safe, 0 = none."""
    n = 0
    while k + n < safe.size and safe[k + n]:
        n += 1
    return n


def delay_ladder(safe, k, start_times):
    """One row per slip of DELAY_SLIPS_H after the headline hour k of safe [starts]: the slipped landing hour, is
    it still safe, and the first safe hour at or after it (None if none before the series ends)."""
    t0 = np.datetime64(str(start_times[k])[:13])
    rows = []
    for slip in DELAY_SLIPS_H:
        j = k + slip
        later = np.flatnonzero(safe[j:]) if j < safe.size else np.array([], int)
        row = {"slip_h": slip, "start_utc": str(t0 + np.timedelta64(slip, "h"))[:13],
               "safe": bool(j < safe.size and safe[j]),
               "next_safe_utc": str(start_times[j + int(later[0])])[:13] if later.size else None}
        if slip == 709:
            row["label"] = LUNATION_LABEL
        rows.append(row)
    return rows


def point_fails(steep, sun_td, earth_td, n_earth, death_h, hours, min_dte_share):
    """The first rule a point fails at one landing hour, in the safe rule's order (council R3 slope gate first);
    None when it passes them all."""
    if steep:
        return "slope"
    if not sun_td:
        return "sun at touchdown"
    if not earth_td:
        return "earth at touchdown"
    if n_earth < min_dte_share * hours:
        return "earth for the mission"
    if death_h >= 0:
        return "battery"
    return None


def miss_table(rows, nb, parent_x, parent_y, s_nb, e_nb, met_nb, m, k, hours, min_dte_share):
    """The points within 100 m of one site (rows into the nb arrays) at landing hour k, mast m: is each safe, and
    the first rule each unsafe point fails. met_nb, s_nb, e_nb come from neighbour_safe(details=True)."""
    out = []
    for p in rows:
        fails = point_fails(float(nb["slope"][p]) >= GATE_SLOPE, bool(s_nb[p, m, k] > 0.5), bool(e_nb[p, m, k]),
                            int(met_nb["n_earth"][p, m, k]), int(met_nb["death_h"][p, m, k]), hours, min_dte_share)
        out.append({"point": str(nb["id"][p]), "dx_m": round(float(nb["x"][p]) - parent_x, 1),
                    "dy_m": round(float(nb["y"][p]) - parent_y, 1),
                    "safe": bool(met_nb["safe"][p, m, k]), "fails": fails})
    return out


BASIS_WORDS = {"within 100 m": "within 100 m",
               "exact point": "on the exact point (no date here is safe if the lander misses by 100 m)"}


def risk_words(margin, ladder, miss, lon, slope_of, basis):
    """The risk block in plain English: how late a landing can be, and what a 100 m miss does. slope_of maps a
    point id to its slope over 100 m, for the slope sentence; basis ("within 100 m" or "exact point") is the rule
    the delays were counted on, the same one that chose the headline landing."""
    first_bad = next((row for row in ladder if not row["safe"]), None)
    late = (f"Land up to {margin - 1} h late and it is still safe {BASIS_WORDS[basis]}" if margin > 1
            else f"Only the headline hour itself is safe {BASIS_WORDS[basis]}")
    if first_bad is None:
        words = [f"{late}; even one lunation later (709 h) is safe."]
    else:
        tail = (f"the next safe hour is {first_bad['next_safe_utc']} UTC" if first_bad["next_safe_utc"]
                else "no later landing hour before the data ends is safe")
        words = [f"{late}; a {first_bad['slip_h']} h slip is not: {tail}."]
    if miss is not None:
        n_ok = sum(row["safe"] for row in miss)
        if n_ok == len(miss):
            words.append(f"Missed by up to 100 m: all {len(miss)} points safe.")
        else:
            row = next(row for row in miss if not row["safe"])
            dist = (row["dx_m"] ** 2 + row["dy_m"] ** 2) ** 0.5
            theta = float(np.degrees(np.arctan2(row["dy_m"], row["dx_m"])))
            where = (f"the point {dist:.0f} m toward bearing {bearing(theta, lon):.0f} deg" if dist
                     else "the target point itself")
            why = row["fails"] + (f" ({slope_of[row['point']]:.1f} deg)" if row["fails"] == "slope" else "")
            words.append(f"Missed by up to 100 m: {n_ok} of {len(miss)} points safe; {where} fails on {why}.")
    return words


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
    firm = firm_touchdown(H, sky, a.earth_margin)[..., : len(starts)]   # at the site's own point, like the report
    order = best_dates(met, firm, hours, a.dates)               # [dates, sites, masts]
    need_Wh = battery_needed(met, battery.e_max)               # [sites, masts], worst safe landing hour
    survived_h = np.where(met["death_h"] < 0, hours, met["death_h"]).max(axis=-1)   # longest any date lasts
    rec = recommended_mast(n_safe, masts)
    np.savez_compressed(out / "dates.npz", start_utc=starts, safe=met["safe"], touchdown=met["touchdown"],
                        survives=met["death_h"] < 0, masts_m=np.array(masts))

    lat, lon, slope = (sites[k].astype(float) for k in ("lat", "lon", "slope"))
    passes_gates = (lat <= GATE_LAT) & (slope < GATE_SLOPE)
    complete = ok.all(axis=2)                                   # [sites, masts]
    candidates = [np.flatnonzero(passes_gates & complete[:, m] & (n_safe[:, m] > 0)) for m in range(len(masts))]
    by_mast = [ranking(c, n_safe[:, m], n_safe[:, m], need_Wh[:, m])[: a.top] for m, c in enumerate(candidates)]

    days_100m = np.full((n_sites, len(masts)), np.nan)
    complete_100m = np.zeros((n_sites, len(masts)), bool)
    n_points = np.zeros(n_sites, int)
    rec_100m = np.full(n_sites, np.nan)
    order_100m = safe_100m = None
    slope_100m, steep_100m = np.full(n_sites, np.nan), np.zeros(n_sites, int)
    if a.neighbours:
        nb = read_csv(Path(a.neighbours) / "sites.csv")
        parent_of = nb["parent"].astype(int)
        missing = {i for rows in by_mast for i in rows} - set(parent_of.tolist())
        if missing:
            raise ValueError(f"--neighbours does not cover ranked sites {sorted(ids[list(missing)])[:10]}: "
                             "re-run scripts/make_neighbours.py on this results.json")
        nb_slope = nb["slope"].astype(float)
        safe_100m, complete_100m, n_points, nb_detail = neighbour_safe(a.neighbours, sky, hours, battery,
                                                                       a.earth_margin, a.min_dte_share, parent_of,
                                                                       met["safe"], nb_slope >= GATE_SLOPE,
                                                                       details=True)
        for p in np.unique(parent_of):
            slope_100m[p] = nb_slope[parent_of == p].max()
            steep_100m[p] = int((nb_slope[parent_of == p] >= GATE_SLOPE).sum())
        checked = n_points > 0
        days_100m = np.where(checked[:, None], safe_days(safe_100m), np.nan)
        order_100m = best_dates(met | {"safe": safe_100m}, firm, hours, a.dates)
        rec_100m = np.where(checked, recommended_mast(np.nan_to_num(days_100m), masts), np.nan)
        # only checked sites: an unchecked site's days on its own point would outrank a checked site's 100 m days
        candidates = [c[checked[c]] for c in candidates]
        by_mast = [ranking(c, np.nan_to_num(days_100m[:, m]), n_safe[:, m], need_Wh[:, m])[: a.top]
                   for m, c in enumerate(candidates)]
    ranked = sorted({i for rows in by_mast for i in rows})
    keys = ranking_keys(a.neighbours is not None)
    values = [{"safe_days_within_100m": days_100m[:, m], "safe_landing_days": n_safe[:, m].astype(float),
               "battery_needed_Wh": need_Wh[:, m]} for m in range(len(masts))]
    reasons = [rank_reasons(rows, values[m], ids, keys) for m, rows in enumerate(by_mast)]
    # the headline landing per site and mast: the best one safe within 100 m where that check ran and found one,
    # else the best on the exact point. Every per-mast number and that mast's mission file use it, so they agree.
    use_100m = np.zeros((n_sites, len(masts)), bool) if order_100m is None else         np.take_along_axis(safe_100m, order_100m[0][..., None], axis=-1)[..., 0]
    head = np.where(use_100m, order[0] if order_100m is None else order_100m[0], order[0])     # [sites, masts]
    at_head = {k: np.take_along_axis(v, head[..., None], axis=-1)[..., 0] for k, v in met.items()}

    results = {
        "meta": {
            "version": 4, "provenance": PROVENANCE, "sky_source": str(sky["script_version"]) + " (NASA SPICE, DE421)",
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
                           "when that check ran, each point also on ground under 10 deg over 100 m; a site with none "
                           "there stays, below the others), then the most "
                           "safe days on the site's own point, then the least battery needed",
                "battery_needed_Wh": "the most battery energy any safe landing hour draws: a full charge minus the "
                                     "lowest level during the mission (the battery model, so sunlight that comes back "
                                     f"partway counts); at most {battery.e_max - battery.e_min:g} Wh by the safe rule",
                "default_mast": "2 m: the best-fit observer height when the engine is checked against NASA's maps",
                "recommended_mast_m": "the shortest mast with at least one safe landing date (information only)",
                "fields": "per-mast numbers are for that mast's headline landing (headline_start): the best one "
                          "safe within 100 m where that check found one, else the best on the exact point; null if "
                          "the mast has no safe landing. detail_file is that landing's full mission"},
            "top_sites_by_mast": {str(mast): ids[rows].tolist() for mast, rows in zip(masts, by_mast)},
            "ranking_keys": [{"field": f, "words": w, "better": b} for f, w, b in keys]},
        "sites": []}
    for i in range(n_sites):
        site = {"id": ids[i], "lat": r(lat[i], 5), "lon": r(lon[i], 4),
                "x_m": r(float(sites["x"][i]), 1), "y_m": r(float(sites["y"][i]), 1), "slope_deg": r(slope[i], 1),
                "passes_gates": bool(passes_gates[i]), "recommended_mast_m": r(rec[i], 1),
                "recommended_mast_100m_m": r(rec_100m[i], 1), "landing_error_points": int(n_points[i]),
                "slope_max_within_100m_deg": r(slope_100m[i], 1),
                "steep_points_within_100m": int(steep_100m[i]) if n_points[i] else None,
                "masts": {}}
        for m, mast in enumerate(masts):
            best = n_safe[i, m] > 0
            pick = lambda k, f=lambda v: v: f(at_head[k][i, m]) if best else None
            site["masts"][str(mast)] = {
                "rank": by_mast[m].index(i) + 1 if i in by_mast[m] else None,
                "rank_reason": reasons[m].get(i),
                "headline_start": str(starts[head[i, m]])[:13] if best else None,
                "headline_within_100m": bool(use_100m[i, m]) if best else None,
                "detail_file": f"sites/{ids[i]}_{mast}.json" if best and i in ranked else None,
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
    if detail.exists():                                # files from an earlier run would point at other sites
        shutil.rmtree(detail)
    detail.mkdir()
    for i in ranked:                                   # every mast with a safe landing, at its headline landing
        info = {key: results["sites"][i][key] for key in ("id", "lat", "lon", "x_m", "y_m", "slope_deg")}
        for m, mast in enumerate(masts):
            f = results["sites"][i]["masts"][str(mast)]["detail_file"]
            if f is None:
                continue
            k = int(head[i, m])
            track = {key: sky[key][i, k: k + hours] for key in TRACK}
            track |= {key: sky[key][k: k + hours] for key in ("time_utc", "sun_radius_deg", "earth_radius_deg")}
            report = site_report(info, H[i, m], D[i, m], ok[i, m], track, mast, battery, a.earth_margin)
            # the risk block (failsafe spec, commit 1): only here, because only this script has the multi-year
            # safe arrays and the 17 points; analyze.py files carry no risk block (a documented scope)
            checked = a.neighbours and n_points[i] > 0
            # delays are counted on the rule that chose the headline: within 100 m when a date is safe there
            basis = "within 100 m" if use_100m[i, m] else "exact point"
            safe_line = safe_100m[i, m] if use_100m[i, m] else met["safe"][i, m]
            margin = consecutive_safe(safe_line, k)
            ladder = delay_ladder(safe_line, k, starts)
            miss = slope_of = None
            if checked:
                rows_p = np.flatnonzero(parent_of == i)
                miss = miss_table(rows_p, nb, float(sites["x"][i]), float(sites["y"][i]),
                                  nb_detail["s"], nb_detail["e"], nb_detail["met"], m, k, hours, a.min_dte_share)
                slope_of = {str(nb["id"][p]): float(nb["slope"][p]) for p in rows_p}
            report["risk"] = {"basis": basis, "delay_margin_h": int(margin), "delay_ladder": ladder,
                              "miss_table": miss, "words": risk_words(margin, ladder, miss, float(lon[i]), slope_of,
                                                                      basis)}
            (out / f).write_text(json.dumps(report))

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
