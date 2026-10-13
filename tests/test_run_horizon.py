import json
import sys

import numpy as np

from horizon.reference import horizon_profile
from horizon.terrain import single
from scripts import make_demo_sites, run_horizon
from test_sites import cone_dem


def test_demo_sites_to_horizon_files(tmp_path, monkeypatch):
    """End to end: make_demo_sites.py writes sites.csv, run_horizon.py turns it into the Step 1 files."""
    dem = cone_dem()
    for module in (make_demo_sites, run_horizon):
        monkeypatch.setattr(module, "read_polar_dem", lambda path, bounds=None: dem)
    lat, lon = dem.rowcol_to_latlon(150, 250)
    monkeypatch.setattr(sys, "argv", ["make_demo_sites.py", "fake.lbl", "--out", str(tmp_path / "sites.csv"),
                                      "--lat", str(lat), "--lon", str(lon), "--n", "3", "--step", "5"])
    make_demo_sites.main()
    monkeypatch.setattr(sys, "argv", ["run_horizon.py", "fake.lbl", str(tmp_path / "sites.csv"), "--out", str(tmp_path),
                                      "--masts", "0", "2", "--dmax", "2000", "--n-az", "90"])
    run_horizon.main()

    H, D, ok = (np.load(tmp_path / f) for f in ("horizon.npy", "blocker.npy", "complete.npy"))
    meta = json.loads((tmp_path / "horizon_meta.json").read_text())
    assert H.shape == D.shape == ok.shape == (9, 2, 90)
    assert H.dtype == D.dtype == np.float32 and ok.dtype == bool and ok.all()
    assert {"n_sites", "n_az", "azimuth", "masts_m", "d_max_m", "kappa", "R_m", "dem_files", "sites_file"} <= set(meta)
    assert (meta["n_sites"], meta["n_az"], meta["masts_m"]) == (9, 90, [0.0, 2.0])
    assert (H[:, 0] > H[:, 1]).all()  # mast axis in order: a taller mast sees a lower skyline everywhere
    H_ref, D_ref, _ = horizon_profile(single(dem), *dem.rowcol_to_xy(150, 250), 2.0, 2000.0, 90, 0.002)  # centre site
    assert np.abs(H[4, 1] - H_ref).max() < 1e-5 and np.array_equal(D[4, 1], D_ref.astype(np.float32))

    # --fine: here the "fine" map is the same grid, so splitting the terrain into two levels must change nothing
    monkeypatch.setattr(sys, "argv", sys.argv + ["--fine", "fake.lbl", "--dfine", "1000", "--out", str(tmp_path / "f")])
    run_horizon.main()
    meta = json.loads((tmp_path / "f" / "horizon_meta.json").read_text())
    assert np.array_equal(np.load(tmp_path / "f" / "horizon.npy"), H)
    assert meta["dem_files"] == ["fake.lbl", "fake.lbl"] and meta["dem_starts_m"] == [0.0, 1000.0]
