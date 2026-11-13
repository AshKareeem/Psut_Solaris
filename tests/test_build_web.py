import json

import numpy as np
import pytest
import rasterio
from PIL import Image

from scripts.build_web import R_KM, SLOPE_SCALE, copy_results, moon_relief


def test_relief_encodes_a_northward_rise_as_north_slope(tmp_path):
    rows, cols = 180, 360                                          # 1 deg pixels
    lat = 90.0 - (np.arange(rows) + 0.5)
    step_km = R_KM * np.radians(1.0)
    z = np.repeat((0.05 * lat / 1.0 * step_km)[:, None], cols, axis=1).astype(np.float32)   # rises 0.05 per km north
    src = tmp_path / "z.tif"
    with rasterio.open(src, "w", driver="GTiff", width=cols, height=rows, count=1, dtype="float32") as r:
        r.write(z, 1)
    moon_relief(src, tmp_path / "r.png")
    rgb = np.asarray(Image.open(tmp_path / "r.png"))
    assert np.all(rgb[1:-1, :, 0] == 128)                          # no east slope
    assert np.all(rgb[1:-1, :, 1] == round(128 + SLOPE_SCALE * 0.05))


def _results(tmp_path, version, detail):
    d = tmp_path / "results"
    (d / "sites").mkdir(parents=True)
    (d / "results.json").write_text(json.dumps({"meta": {"version": version},
                                                "sites": [{"id": "1", "masts": {"2.0": {"detail_file": detail}}},
                                                          {"id": "2", "masts": {"2.0": {"detail_file": None}}}]}))
    return d


def test_copy_results_takes_only_the_detail_files_it_names(tmp_path):
    d = _results(tmp_path, 4, "sites/1.json")
    (d / "sites/1.json").write_text("{}")
    (d / "sites/old.json").write_text("{}")                        # left over from an earlier run
    assert copy_results(d, tmp_path / "web/data") == 1
    assert sorted(p.name for p in (tmp_path / "web/data/sites").iterdir()) == ["1.json"]


def test_copy_results_refuses_another_version(tmp_path):
    with pytest.raises(ValueError, match="version 3"):
        copy_results(_results(tmp_path, 3, None), tmp_path / "web/data")


def test_copy_results_fails_if_a_named_detail_file_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        copy_results(_results(tmp_path, 4, "sites/1.json"), tmp_path / "web/data")


def _profile_results(root, pid, made_with):
    d = root / pid
    (d / "sites").mkdir(parents=True)
    (d / "sites/1.json").write_text("{}")
    (d / "results.json").write_text(json.dumps({"meta": {"version": 4, "profile": {"id": made_with}},
                                                "sites": [{"id": "1", "masts": {"2.0": {"detail_file": "sites/1.json"}}}]}))


def test_copy_profiles_puts_the_default_at_the_top_and_indexes_every_preset(tmp_path):
    from scripts.build_web import copy_profiles
    from scripts.profiles import DEFAULT, PROFILES
    for pid in PROFILES:
        _profile_results(tmp_path / "profiles", pid, pid)
    data = tmp_path / "web/data"
    assert copy_profiles(tmp_path / "profiles", data) == len(PROFILES)
    index = json.loads((data / "profiles.json").read_text())
    assert [p["id"] for p in index][0] == DEFAULT and index[0]["results"] == "results.json" and index[0]["default"]
    for p in index[1:]:
        assert p["results"] == f"profiles/{p['id']}/results.json" and not p["default"]
        assert (data / p["results"]).exists() and (data / f"profiles/{p['id']}/sites/1.json").exists()
    assert (data / "sites/1.json").exists()


def test_copy_profiles_refuses_results_made_with_another_preset(tmp_path):
    from scripts.build_web import copy_profiles
    from scripts.profiles import PROFILES
    ids = list(PROFILES)
    for pid in ids:
        _profile_results(tmp_path / "profiles", pid, ids[0] if pid == ids[-1] else pid)
    with pytest.raises(ValueError, match="made with preset"):
        copy_profiles(tmp_path / "profiles", tmp_path / "web/data")
