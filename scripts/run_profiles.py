"""Step 4 for every lander preset (scripts/profiles.py), with the landing-error check, for the web app.

  1. scripts/score_sites.py for each preset (its flags)                          -> <out>/<id>/first/
  2. scripts/make_neighbours.py on all presets' ranked sites, one shared set     -> <out>/nb/sites.csv
  3. scripts/run_horizon.py on those points (20 m terrain near them)             -> <out>/nb/
  4. scripts/score_sites.py --neighbours for each preset                         -> <out>/<id>/
Each final results.json gets meta.profile {id, label, description, args}. Then:
  python scripts/build_web.py --profiles <out>

Usage:
  python scripts/run_profiles.py --horizon out/pipe/horizon --sky out/pipe6/sky.npz --sites out/demo/sites.csv \
      --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/profiles
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.profiles import PROFILES  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent


def run(script, *args):
    print(f"\n>> {script} {' '.join(map(str, args))}", flush=True)
    subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)], check=True)


def tag(results_path, pid):
    """Record which preset a results.json was made with."""
    results = json.loads(results_path.read_text())
    results["meta"]["profile"] = {"id": pid, **PROFILES[pid]}
    results_path.write_text(json.dumps(results))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", required=True, help="Step 1 folder for the sites")
    ap.add_argument("--sky", required=True, help="Step 2 sky.npz for the sites")
    ap.add_argument("--sites", required=True, help="the sites.csv both used")
    ap.add_argument("--coarse", required=True, help="PDS3 label of the 240 m map (for the points within 100 m)")
    ap.add_argument("--fine", required=True, help="PDS3 label of the 20 m map (for the points within 100 m)")
    ap.add_argument("--out", default="out/profiles")
    a = ap.parse_args()

    out = Path(a.out)
    base = ["--horizon", a.horizon, "--sky", a.sky, "--sites", a.sites]
    for pid, p in PROFILES.items():
        run("score_sites.py", *base, *p["args"], "--out", out / pid / "first")
    nb = out / "nb"
    run("make_neighbours.py", a.sites, *[out / pid / "first" / "results.json" for pid in PROFILES],
        "--out", nb / "sites.csv")
    run("run_horizon.py", a.coarse, nb / "sites.csv", "--fine", a.fine, "--out", nb)
    for pid, p in PROFILES.items():
        run("score_sites.py", *base, *p["args"], "--neighbours", nb, "--out", out / pid)
        tag(out / pid / "results.json", pid)
    print(f"\n{len(PROFILES)} presets -> {out}; next: python scripts/build_web.py --profiles {out}")


if __name__ == "__main__":
    main()
