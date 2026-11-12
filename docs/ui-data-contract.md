# Data contract for the web app (BIT)

Two kinds of file. The pipeline writes both; nothing in the app should compute physics.

| File | Made by | What it holds |
|---|---|---|
| `results.json` (version 4) | `scripts/score_sites.py` | every site: one ranking per mast, safe landing days, numbers for its best date |
| `sites/<id>.json` (version 1) | `scripts/score_sites.py` for each top site, at its recommended mast and best date (within 100 m when checked); `scripts/analyze.py` for any coordinates | one site in full: skyline, hourly Sun and Earth tracks, events, battery, verdict and reasons |

Units: degrees, metres (`_m`), kilometres (`_km`), hours (`_h`), watt-hours (`_Wh`). Times are UTC, `YYYY-MM-DDTHH` (hourly) or `YYYY-MM-DDTHH:MM` (events, to the minute).
Directions `theta` / `*_az` are the team convention: degrees from map +x, counterclockwise; 90 = toward longitude 0 (where Earth is). Text in `verdict` and `why` uses compass bearings (clockwise from local north).

## results.json

```
meta
  version 4, sky_source, span {first_start, last_start, n_days}, mission_days, masts_m [0, 2, 5, 10],
  default_mast_m 2, n_az, min_dte_share 0.5, earth_margin_deg, gates {lat_max_deg, slope_max_deg}, landing_error_m 100,
  lander {name, e_max_Wh, e_min_Wh, p_panel_W, p_load_W, bridge_hours, model, sources}
  definitions {safe_landing_date, ranking, bridge_Wh, default_mast, recommended_mast_m, fields}   (words, show as is)
  top_sites_by_mast {"0.0": ["<site id>", ...], ...}   one list per mast: most safe days (within 100 m where
                                                       checked), then the least bridge_Wh; no overall list
sites [ ... one per site, in sites.csv order ... ]
  id, lat, lon, x_m, y_m, slope_deg, passes_gates
  recommended_mast_m        shortest mast with a safe landing date at the point (null: none)
  recommended_mast_100m_m   shortest mast with a date safe everywhere within 100 m (null: not checked or none)
  landing_error_points      points checked within 100 m (0: not checked)
  detail_file               "sites/<id>.json" for ranked sites, else null
  masts {"0.0": {...}, "2.0": {...}, ...}
    safe_landing_days       landing dates (00:00 UTC each day) with power and Earth at touchdown that survive the mission
    best_dates [{start, f_both, longest_dark_h}, ...]   up to 3 safe dates, best first; [] if none
    f_sun, f_earth, f_both  share of mission hours with the Sun up / Earth in view / both, on the best date (null: no safe date)
    longest_dark_h          longest darkness on the best date: the cold soak
    bridge_Wh               energy to get through it at the battery's load
    battery_lowest_Wh
    longest_survival_h      the longest any landing date lasts (= mission hours if some date survives)
    complete                every ray stayed on the terrain map
    safe_days_within_100m   landing dates safe at all 17 points within 100 m (null unless the check ran for this site)
    best_dates_within_100m  up to 3 of those dates, best first
    complete_within_100m    every ray of every point stayed on the map
```

## sites/&lt;id&gt;.json

```
version 1, site {id, lat, lon, x_m, y_m, ...}, mast_m, earth_margin_deg
mission {start_utc, hours}
summary
  touchdown_sun, touchdown_earth, safe_landing, survives, dies_at_hour, battery_lowest_Wh,
  f_sun, f_earth, f_both, longest_dark_h, bridge_Wh, longest_earth_blackout_h
verdict [sentence, ...]     plain English, show as is
why [sentence, ...]         what blocks the Sun in the darkest spell and Earth in the longest blackout,
                            with the distance and bearing of the terrain; a note if rays left the map
events
  sunlit [{start, end}], dte [{start, end}], both [{start, end}]
                            start/end to the minute; null = before/after the mission window
  hours_to_sunset, hours_to_earthset    from the landing time (0: already down; null: not before the end)
skyline                     the "skyline view" screen
  theta_deg [n_az], horizon_deg [n_az], blocker_km [n_az], complete [n_az]
hourly                      one entry per mission hour
  time_utc, sun_az, sun_el, sun_clearance_deg, earth_az, earth_el, earth_clearance_deg,
  sun_fraction (0-1), earth_visible, battery_Wh
```

Drawing the skyline view: plot `horizon_deg` against `theta_deg`, then the Sun track (`sun_az`, `sun_el`) and Earth track (`earth_az`, `earth_el`) on the same axes. `sun_clearance_deg` is how high the Sun stands above the skyline ("solar elevation", objective 4); `hours_to_sunset` answers "how much time remains before sunset or Earthset" (objective 3).

## The app's folder (`web/`)

`scripts/build_web.py --results <score_sites --out>` copies `results.json` and the detail files it names into `web/data/`, `named_sites.csv` into `web/data/named_sites.json`, and builds the Moon textures in `web/assets/`. The page fails loudly if a file is missing; it never shows stand-in data.

## Hand-set missions: `POST /api/mission` (`scripts/serve.py`)

Body (all required): `lat, lon, terrain ("20m" | "240m"), mast_m, start_utc (YYYY-MM-DDTHH), days, e_max_Wh, e_min_Wh, p_panel_W, p_load_W, earth_margin_deg`.
Answer: the `sites/<id>.json` report from `scripts/analyze.py` (site also carries `ground_m`, `slope_deg` over 100 m and `terrain`, the maps used), plus `mission_inputs` (the body as run). A bad body gets HTTP 400 `{"error": "<reason>"}`. It needs the LOLA maps, the SPICE kernels and 1-3 s of compute, so it runs on a laptop, not in the browser.
