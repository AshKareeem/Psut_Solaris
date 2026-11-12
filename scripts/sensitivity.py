"""How much the answers depend on the two weakest inputs: the battery size and the antenna's view of Earth.

For every site and mast:
  safe landing days (scripts/score_sites.py rules) with the lander's battery at each --e-max size, everything else
  as in the lander profile (scripts/battery.py), with Earth's any-part-visible rule
  share of all hours with Earth in view for an antenna that needs 0 deg and each --masks clearance above the skyline
Writes sensitivity.json. The battery profile is a stated estimate, so this shows which conclusions survive a
battery 2x or 4x bigger, and how much a real antenna mask costs.

Usage:
  python scripts/sensitivity.py --horizon out/run/horizon --sky out/run/sky.npz --sites sites.csv --out out/run/results
"""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.battery import Battery  # noqa: E402
from scripts.score_sites import date_metrics, load, visibility  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", required=True)
    ap.add_argument("--sky", required=True)
    ap.add_argument("--sites", required=True)
    ap.add_argument("--out", required=True, help="folder for sensitivity.json")
    ap.add_argument("--days", type=int, default=14, help="mission length")
    ap.add_argument("--min-dte-share", type=float, default=0.5)
    ap.add_argument("--e-max", type=float, nargs="+", default=[700.0, 1400.0, 2800.0], help="battery sizes (Wh)")
    ap.add_argument("--masks", type=float, nargs="+", default=[2.0], help="antenna masks (deg) besides 0")
    a = ap.parse_args()

    meta, H, _, _, sky, sites = load(a.horizon, a.sky, a.sites)
    masts, hours, lander = [float(m) for m in meta["masts_m"]], a.days * 24, Battery()
    s, e, b = visibility(H, sky, 0.0)
    safe_days = {}
    for e_max in a.e_max:                       # e_min stays the same share of a full battery
        battery = replace(lander, e_max=e_max, e_min=e_max * lander.e_min / lander.e_max)
        safe_days[e_max] = date_metrics(s, e, b, hours, battery, a.min_dte_share)["safe"].sum(-1)
        print(f"battery {e_max:g} Wh: bridges {battery.bridge_hours():.1f} h; sites with a safe date per mast "
              + ", ".join(f"{m:g} m: {(safe_days[e_max][:, i] > 0).sum()}" for i, m in enumerate(masts)))
    dte = {0.0: e.mean(-1)}
    for mask in a.masks:
        dte[mask] = visibility(H, sky, mask)[1].mean(-1)
        print(f"antenna mask {mask:g} deg: Earth in view {np.median(dte[mask]):.0%} of the time at the median "
              f"site and mast (0 deg: {np.median(dte[0.0]):.0%})")

    out = {
        "meta": {"version": 1, "lander": lander.profile(), "mission_days": a.days, "min_dte_share": a.min_dte_share,
                 "e_max_Wh": a.e_max, "e_min_rule": "same share of a full battery as the lander profile",
                 "masks_deg": [0.0] + a.masks, "span": [str(sky["time_utc"][0])[:13], str(sky["time_utc"][-1])[:13]],
                 "definitions": {"safe_days_by_e_max": "safe landing days with the battery at each size",
                                 "dte_share_by_mask": "share of all hours with Earth in view for an antenna that "
                                                      "needs that many degrees of clearance above the skyline"}},
        "sites": [{"id": str(sites["id"][i]), "masts": {str(m): {
            "safe_days_by_e_max": {f"{v:g}": int(safe_days[v][i, j]) for v in a.e_max},
            "dte_share_by_mask": {f"{k:g}": round(float(dte[k][i, j]), 3) for k in dte}}
            for j, m in enumerate(masts)}} for i in range(H.shape[0])]}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "sensitivity.json").write_text(json.dumps(out))
    print(f"-> {Path(a.out) / 'sensitivity.json'}")


if __name__ == "__main__":
    main()
