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
  definitions {safe_landing_date, ranking, battery_needed_Wh, default_mast, recommended_mast_m, fields}   (words, show as is)
  top_sites_by_mast {"0.0": ["<site id>", ...], ...}   one list per mast: most safe days (within 100 m when that
                                                       check ran: then only checked sites, and a site with 0 days
                                                       within 100 m stays below the others), then the least
                                                       battery_needed_Wh; no overall list
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
    battery_needed_Wh       the most any safe landing hour draws from the battery: e_max - lowest level (null: none)
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
  f_sun, f_earth, f_both, longest_dark_h, battery_needed_Wh (e_max - battery_lowest_Wh), longest_earth_blackout_h,
  marginal                  the Sun's centre or Earth's top clears the skyline by under 0.5 deg at touchdown
verdict [sentence, ...]     plain English, show as is
why [sentence, ...]         a marginal touchdown and what sets that skyline; for a body that never sets, its
                            closest pass and the terrain there; otherwise what blocks the Sun in the darkest
                            spell and Earth in the longest blackout (distance and bearing); a note if rays left
                            the map
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

`scripts/build_web.py --profiles <run_profiles --out>` copies every lander preset's `results.json` and the detail files it names into `web/data/`, `named_sites.csv` into `web/data/named_sites.json`, and builds the Moon textures in `web/assets/`. The page fails loudly if a file is missing; it never shows stand-in data.

### Lander presets ("Your lander"): `web/data/profiles.json`

A list, the default first:

```json
[{"id": "nova-c-14d", "label": "Nova-C-class lander, 14-day mission", "description": "...",
  "results": "results.json", "default": true},
 {"id": "nova-c-28d", "label": "Long mission: 28 days", "description": "...",
  "results": "profiles/nova-c-28d/results.json", "default": false},
 {"id": "weak-antenna", "label": "Weak antenna: Earth 2° above the horizon", "description": "...",
  "results": "profiles/weak-antenna/results.json", "default": false}]
```

- **Each preset is a complete `results.json`**, the same schema as above. Choosing a preset means loading its file and redrawing the ranking, map, site panel and compare view from it. The browser computes nothing.
- **Paths are relative to `web/data/`.** A preset's `detail_file` values (`sites/<id>.json`) are relative to *its own* `results.json` folder. For example, `nova-c-28d`'s site 190 is `data/profiles/nova-c-28d/sites/190.json`.
- Each `results.json` names its preset in `meta.profile` (`id`, `label`, `description`, `args`). `meta.mission_days` and `meta.earth_margin_deg` change with the preset, so read them, never assume 14 and 0.
- Show `label` in the dropdown and `description` under it. **No weights, no sliders:** the presets are mission requirements.

## Hand-set missions: `POST /api/mission` (`scripts/serve.py`)

Body (all required): `lat, lon, terrain ("20m" | "240m"), mast_m, start_utc (YYYY-MM-DDTHH), days, e_max_Wh, e_min_Wh, p_panel_W, p_load_W, earth_margin_deg`.
Answer: the `sites/<id>.json` report from `scripts/analyze.py` (site also carries `ground_m`, `slope_deg` over 100 m and `terrain`, the maps used), plus `mission_inputs` (the body as run). A bad body gets HTTP 400 `{"error": "<reason>"}`. It needs the LOLA maps, the SPICE kernels and 1-3 s of compute, so it runs on a laptop, not in the browser.
