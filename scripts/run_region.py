"""The whole south-polar region, not just the demo grid: every candidate site in a sites.csv (e.g. IoT's 2,436
sites, 5 km apart, within 6 deg of the pole) through the full pipeline, tile by tile, then one regional summary.

Why tiles: the pipeline holds every landing hour of 2026-2030 for every site, mast and hour in memory (about 4 MB per
site) and crops the 20 m map to the sites +- 40 km; the whole region at once needs ~10 GB. Tiles of a few hundred
sites keep each step under ~1.5 GB, and each tile is the ordinary pipeline (one code path):

  per tile: slope over 100 m (named_to_sites.height_and_slope, the 20 m map) -> run_horizon.py -> make_sky.py ->
            score_sites.py -> make_neighbours.py -> run_horizon.py (17 points within 100 m) -> score_sites.py --neighbours
  then:     region_summary.json: per mast, every ranked site of every tile, ordered by the ranking's own keys
            (safe days within 100 m, then on the point, then battery needed)

Usage:
  python scripts/run_region.py --sites Team_Work/IOT/sites.csv --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/region
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizon.dem import read_polar_dem  # noqa: E402
from horizon.sites import COLUMNS  # noqa: E402
from scripts.named_to_sites import BASELINE_M, height_and_slope  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
D_PAD = 1000.0   # m around a tile's sites for the slope crop (the engine crops its own, larger, window)


def tiles(x, y, n):
    """Indices of the sites in each of n x n equal map tiles over their bounding box; every site in exactly one."""
    ix = np.minimum(((x - x.min()) / (np.ptp(x) or 1) * n).astype(int), n - 1)
    iy = np.minimum(((y - y.min()) / (np.ptp(y) or 1) * n).astype(int), n - 1)
    return [np.flatnonzero((ix == i) & (iy == j)) for j in range(n) for i in range(n)]


def write_tile(rows, idx, fine, path):
    """The tile's sites, each with its slope over 100 m on the finest map (the gate's quantity)."""
    xs = np.array([float(rows[i]["x"]) for i in idx])
    ys = np.array([float(rows[i]["y"]) for i in idx])
    pad = BASELINE_M + D_PAD
    dem = read_polar_dem(fine, bounds=(xs.min() - pad, xs.max() + pad, ys.min() - pad, ys.max() + pad))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for i, x, y in zip(idx, xs, ys):
            height, slope = height_and_slope(dem, x, y)
            w.writerow([rows[i]["id"], rows[i]["x"], rows[i]["y"], rows[i]["lat"], rows[i]["lon"], f"{height:.2f}",
                        f"{slope:.2f}"])


def run(script, *args):
    print(">>", script, *args, flush=True)
    subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], check=True)


def summary(results_files):
    """Per mast, every ranked site of every tile in the ranking's order, with what decides it."""
    out, metas = {}, []
    for f in results_files:
        r = json.loads(Path(f).read_text())
        metas.append(r["meta"])
        by_id = {s["id"]: s for s in r["sites"]}
        for mast, ids in r["meta"]["top_sites_by_mast"].items():
            for sid in ids:
                s, e = by_id[sid], by_id[sid]["masts"][mast]
                out.setdefault(mast, []).append({
                    "id": sid, "lat": s["lat"], "lon": s["lon"], "slope_deg": s["slope_deg"],
                    "slope_max_within_100m_deg": s["slope_max_within_100m_deg"],
                    "safe_days_within_100m": e["safe_days_within_100m"], "safe_landing_days": e["safe_landing_days"],
                    "battery_needed_Wh": e["battery_needed_Wh"], "headline_start": e["headline_start"]})
    for mast in out:
        out[mast].sort(key=lambda s: (-(s["safe_days_within_100m"] or 0), -s["safe_landing_days"],
                                      s["battery_needed_Wh"] if s["battery_needed_Wh"] is not None else 1e9, s["id"]))
    return out, metas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", required=True)
    ap.add_argument("--coarse", required=True)
    ap.add_argument("--fine", required=True)
    ap.add_argument("--tiles", type=int, default=3, help="n x n tiles")
    ap.add_argument("--start", default="2026-01-01")
    ap.add_argument("--days", type=int, default=1826, help="days of landing hours (sky file)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    with open(a.sites, newline="") as f:
        rows = list(csv.DictReader(f))
    x = np.array([float(r["x"]) for r in rows])
    y = np.array([float(r["y"]) for r in rows])
    out = Path(a.out)
    done = []
    for k, idx in enumerate(tiles(x, y, a.tiles)):
        if not idx.size:
            continue
        t = out / f"tile{k}"
        if (t / "results" / "results.json").exists():          # a finished tile from an interrupted run
            done.append(t / "results" / "results.json")
            continue
        write_tile(rows, idx, a.fine, t / "sites.csv")
        run("run_horizon.py", a.coarse, t / "sites.csv", "--fine", a.fine, "--out", t / "horizon")
        run("make_sky.py", "--sites", t / "sites.csv", "--start", a.start, "--days", a.days, "--out", t / "sky.npz")
        base = ["--horizon", t / "horizon", "--sky", t / "sky.npz", "--sites", t / "sites.csv"]
        run("score_sites.py", *base, "--out", t / "first")
        if not any(json.loads((t / "first" / "results.json").read_text())["meta"]["top_sites_by_mast"].values()):
            run("score_sites.py", *base, "--out", t / "results")       # nothing ranked: no 100 m check to run
        else:
            run("make_neighbours.py", t / "sites.csv", t / "first" / "results.json", "--slope-dem", a.fine,
                "--out", t / "nb" / "sites.csv")
            run("run_horizon.py", a.coarse, t / "nb" / "sites.csv", "--fine", a.fine, "--out", t / "nb")
            run("score_sites.py", *base, "--neighbours", t / "nb", "--out", t / "results")
        (t / "sky.npz").unlink()                                       # ~200 MB per tile; rebuilt in seconds
        done.append(t / "results" / "results.json")

    ranked, metas = summary(done)
    n_sites = sum(len(json.loads(Path(f).read_text())["sites"]) for f in done)
    n_gates = sum(sum(s["passes_gates"] for s in json.loads(Path(f).read_text())["sites"]) for f in done)
    res = {"sites": n_sites, "pass_gates": n_gates, "tiles": [str(f) for f in done], "span": metas[0]["span"],
           "lander": metas[0]["lander"], "ranking_keys": metas[0]["ranking_keys"], "ranked_by_mast": ranked}
    (out / "region_summary.json").write_text(json.dumps(res, indent=1))
    print(f"{n_sites} sites in {len(done)} tiles, {n_gates} pass the gates -> {out / 'region_summary.json'}")
    for mast, lst in ranked.items():
        top = ", ".join(f"{s['id']} ({s['safe_days_within_100m']}/{s['safe_landing_days']})" for s in lst[:5])
        print(f"  mast {mast} m: {len(lst)} ranked; best (days within 100 m / on the point): {top}")


if __name__ == "__main__":
    main()
