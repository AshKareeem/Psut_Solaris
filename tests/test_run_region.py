import numpy as np

from scripts.run_region import summary, tiles


def test_tiles_put_every_site_in_exactly_one_tile():
    rng = np.random.default_rng(1)
    x, y = rng.uniform(-180e3, 180e3, 500), rng.uniform(-180e3, 180e3, 500)
    groups = tiles(x, y, 3)
    assert len(groups) == 9 and sorted(np.concatenate(groups).tolist()) == list(range(500))
    assert all(np.ptp(x[g]) <= 120e3 + 1 and np.ptp(y[g]) <= 120e3 + 1 for g in groups if g.size)


def test_summary_orders_sites_from_all_tiles_by_the_ranking_keys(tmp_path):
    def site(i, within, point, need):
        return {"id": i, "lat": -89.0, "lon": 0.0, "x_m": 0.0, "y_m": 30000.0, "slope_deg": 3.0, "slope_max_within_100m_deg": 5.0,
                "masts": {"5.0": {"safe_days_within_100m": within, "safe_landing_days": point,
                                  "battery_needed_Wh": need, "headline_start": "2026-01-01T00"}}}
    files = []
    for k, sites in enumerate([[site("a", 0, 300, 500.0), site("b", 40, 90, 550.0)], [site("c", 40, 120, 560.0)]]):
        f = tmp_path / f"r{k}.json"
        f.write_text(__import__("json").dumps({"meta": {"top_sites_by_mast": {"5.0": [s["id"] for s in sites]}},
                                               "sites": sites}))
        files.append(f)
    ranked, _ = summary(files)
    assert [s["id"] for s in ranked["5.0"]] == ["c", "b", "a"]   # 100 m days, then days on the point
