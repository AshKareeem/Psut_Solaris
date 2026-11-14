# The whole region: all 2,436 candidate sites within 6° of the pole

**Who this is for:** the team, judges who ask "is it only one crater?", and anyone reproducing our results.

Run on Sat Nov 14 with `scripts/run_region.py`: IoT's grid of 2436 sites, 5 km apart. Each went through the same pipeline as the demo: skylines on NASA LOLA (20 m within 40 km, 240 m to 250 km), NASA SPICE every hour 2026–2030, the Nova-C-class lander for 14 days, and the 17-point check within 100 m, slopes included. 2385 sites pass the gates (within 6° and under 10° over 100 m). No ray left the terrain map.

| Height | Sites with at least one safe landing day | Sites still safe if the lander misses by 100 m (at least) |
|---|---|---|
| 0 m | 74 | 3 |
| 2 m | 116 | 49 |
| 5 m | 147 | 74 |
| 10 m | 168 | 98 |

**At least:** each tile's top 20 sites per height got the 100 m check (the same rule as the demo grid), so the last column is a floor.

## Best sites at 2 m

| Rank | Site | Latitude, longitude | Slope (°) / steepest within 100 m | Safe days within 100 m | Safe days on the point | Best landing (UTC) |
|---|---|---|---|---|---|---|
| 1 | 422 | -87.047°, -24.187° | 2.7 / 5.8 | 77 | 156 | 2027-11-05T06 |
| 2 | 159 | -85.275°, -23.291° | 4.7 / 9.1 | 59 | 76 | 2026-09-22T01 |
| 3 | 160 | -85.337°, -21.431° | 8.6 / 9.9 | 55 | 134 | 2026-08-25T21 |
| 4 | 169 | -85.033°, 29.104° | 1.5 / 5.7 | 50 | 69 | 2026-10-19T03 |
| 5 | 152 | -84.354°, 37.082° | 1.6 / 4.8 | 50 | 52 | 2026-10-17T23 |
| 6 | 151 | -84.452°, 35.724° | 6.7 / 9.7 | 46 | 52 | 2026-01-24T22 |
| 7 | 125 | -84.886°, 24.076° | 5.7 / 6.6 | 44 | 102 | 2027-11-05T23 |
| 8 | 1113 | -87.784°, -97.103° | 2.7 / 6.3 | 43 | 62 | 2029-06-27T17 |

## Best sites at 5 m

| Rank | Site | Latitude, longitude | Slope (°) / steepest within 100 m | Safe days within 100 m | Safe days on the point | Best landing (UTC) |
|---|---|---|---|---|---|---|
| 1 | 422 | -87.047°, -24.187° | 2.7 / 5.8 | 149 | 162 | 2027-11-05T05 |
| 2 | 160 | -85.337°, -21.431° | 8.6 / 9.9 | 117 | 136 | 2026-08-25T19 |
| 3 | 125 | -84.886°, 24.076° | 5.7 / 6.6 | 92 | 111 | 2026-11-16T19 |
| 4 | 159 | -85.275°, -23.291° | 4.7 / 9.1 | 89 | 110 | 2026-08-23T18 |
| 5 | 392 | -86.896°, -22.940° | 2.9 / 5.1 | 84 | 102 | 2026-09-23T20 |
| 6 | 540 | -87.114°, -40.366° | 4.7 / 7.3 | 74 | 99 | 2026-08-26T17 |
| 7 | 149 | -84.888°, 28.206° | 3.7 / 4.3 | 74 | 98 | 2026-10-19T10 |
| 8 | 1587 | -85.184°, -115.676° | 2.2 / 3.5 | 73 | 94 | 2028-07-08T16 |

## Best sites at 10 m

| Rank | Site | Latitude, longitude | Slope (°) / steepest within 100 m | Safe days within 100 m | Safe days on the point | Best landing (UTC) |
|---|---|---|---|---|---|---|
| 1 | 422 | -87.047°, -24.187° | 2.7 / 5.8 | 162 | 172 | 2026-11-16T23 |
| 2 | 64 | -84.228°, 26.555° | 4.4 / 8.2 | 141 | 150 | 2026-01-24T16 |
| 3 | 160 | -85.337°, -21.431° | 8.6 / 9.9 | 134 | 136 | 2026-08-25T18 |
| 4 | 1116 | -89.234°, -110.963° | 7.1 / 10.0 | 114 | 146 | 2026-08-27T09 |
| 5 | 159 | -85.275°, -23.291° | 4.7 / 9.1 | 114 | 142 | 2026-08-23T17 |
| 6 | 857 | -88.450°, -62.514° | 3.1 / 5.1 | 113 | 135 | 2026-10-20T20 |
| 7 | 125 | -84.886°, 24.076° | 5.7 / 6.6 | 107 | 126 | 2026-10-19T16 |
| 8 | 18 | -84.123°, 15.716° | 2.2 / 8.1 | 102 | 119 | 2026-01-26T05 |

## What this adds, and what it doesn't

- **The demo grid isn't the whole story.** Around the Shackleton rim no site survives a 100 m miss at 2 m. Region-wide, at least 49 sites do. The best, **site 422** (87.047°S, 24.187°W, ground 2.7°, steepest within 100 m 5.8°), keeps 77 safe landing days at 2 m, 149 at 5 m and 162 at 10 m.
- **Played live through "Plan your own mission"** (`scripts/analyze.py`, 2 m, landing 2027-11-05 06:00 UTC, 14 days): safe. At touchdown the Sun is 2.16° and Earth 0.54° above the skyline, both stay in view the whole mission, and it survives on half the battery (at best). Saved as `out/analyze/site422_2m.json`.
- **Checked against NASA PGDA at site 422** (the 3×3 NASA 60 m pixels around it; an 18.6-year average, observer height unstated):
  - Earth in view: ours 55.8% at 2 m, NASA 54–55%;
  - sunlight: ours 48% at 2 m, NASA 31–47% across the 9 pixels and 46.6% on the site's own pixel.
  - Our window is 2026–2030, so a few points of difference are expected. Our Sun share is slightly above NASA's 9-pixel range, so say "within a few points", not "matches".
- **Limits:**
  - Sites more than 5° from the pole are beyond our convergence study (300 km test rays leave the 240 m map there); great-circle rays keep the 99% error small there, but unverified.
  - NASA Moon Trek's 5 m map covers only 87.5–90°S, so site 422 (87.05°S) can't get the 5 m check our demo site had.
  - The lander is the same sun-tracking upper bound everywhere.
- **Reproduce:** `python scripts/run_region.py --sites Team_Work/IOT/sites.csv --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --tiles 4 --out out/region` (about 70 minutes on a laptop; `out/region/region_summary.json`).
