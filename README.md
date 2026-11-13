# LunarWindow: Lunar Landing Site Navigator (NASA Space Apps 2026, team Psut_Solaris)

Challenge: [Lunar Landing Site Navigator](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/) (it was called "CLPS Lunar Mission Browser" until the full statement came out; the old link is dead).

From candidate landing sites near the Moon's south pole to ranked sites with **safe landing dates** (power and Earth at touchdown, and the lander lives through the mission), sunrise/sunset and direct-to-Earth windows to the minute, the longest darkness and the energy to bridge it, landing-error robustness within 100 m and a mast recommendation, for the web app. Any coordinates and landing time get the same report from one call (`scripts/analyze.py`). The core is the horizon engine (Step 1), which computes each site's **skyline**: for every direction θ, the horizon elevation H(θ) and the distance to the terrain that blocks the sky.

## The pipeline, end to end

| Step | What | Code | Owner |
|---|---|---|---|
| 0 | candidate sites (`sites.csv`: id, x, y, lat, lon, height, slope) | IoT | IoT |
| 1 | skylines per site and mast (great circles, 20 m + 240 m terrain) | `scripts/run_horizon.py` | Ash |
| 2 | Sun and Earth positions every hour (NASA SPICE) | `scripts/make_sky.py`, `docs/step2-sky.md` | CE 2 |
| 3–4 | visibility, safe landing dates, battery, mast, ranking, landing error | `scripts/score_sites.py`, `scripts/battery.py`, `scripts/events.py` | CE 3, IoT |
| — | one site in full: skyline, tracks, events, verdict (`sites/<id>.json`) | `scripts/site_report.py`; any coordinates: `scripts/analyze.py` | |
| — | web app on `results.json` and `sites/<id>.json` (`docs/ui-data-contract.md`); hand-set missions through `scripts/analyze.py` | `web/`, `scripts/build_web.py`, `scripts/serve.py` | BIT |

```
python scripts/run_horizon.py data/ldem_75s_240m.lbl sites.csv --fine data/ldem_80s_20m.lbl --out out/run/horizon
python scripts/make_sky.py --sites sites.csv --start 2026-01-01 --days 1826 --out out/run/sky.npz
python scripts/score_sites.py --horizon out/run/horizon --sky out/run/sky.npz --sites sites.csv --out out/run/results
python scripts/make_neighbours.py sites.csv out/run/results/results.json --out out/run/nb/sites.csv
python scripts/run_horizon.py data/ldem_75s_240m.lbl out/run/nb/sites.csv --fine data/ldem_80s_20m.lbl --out out/run/nb
python scripts/score_sites.py --horizon out/run/horizon --sky out/run/sky.npz --sites sites.csv --neighbours out/run/nb --out out/run/results
```

- The first two commands are independent; the last three add the landing-error check (17 points within 100 m of each top site).
- **Lander presets ("Your lander" in the web app):** `scripts/profiles.py` lists them. Each is a set of mission requirements, never weights: the default Nova-C-class lander for 14 days, the same lander for 28 days, and a weak antenna that needs Earth 2° above the horizon. `scripts/run_profiles.py` runs the last four commands for every preset, with one shared landing-error run:

  ```
  python scripts/run_profiles.py --horizon out/run/horizon --sky out/run/sky.npz --sites sites.csv --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/run/profiles
  ```
- The sky covers 2026–2030, the years CLPS and Artemis III plan to fly: 1,812 landing dates per site. On the 400 demo sites that's a 235 MB sky file, 12 s for the sky and about 2 minutes for the rest. Sites beyond about 36 km from the pole need `ldem_80s_20m` (1.85 GB, same PDS folder as the other maps).
- **No weighted score.** Every number is physical:
  - A **safe landing date** has more than half the Sun visible and Earth in view in the landing hour, Earth in view for at least half the mission (`--min-dte-share`, no relay), and the battery never drops below its floor during the mission. `safe_landing_days` counts them: the official text's "launch delays ... alternative dates" as a number.
  - **One ranking per mast height** (`top_sites_by_mast`): most safe landing days (within 100 m where checked), then the least battery needed for the longest darkness. The **recommended mast** (the shortest mast with a safe landing date) is information only.
  - **Within 100 m** (`--neighbours`): a lander aimed at a site comes down anywhere within 100 m, so a date counts only if it is safe at all 17 points there. The checked sites then rank on those days; one safe on its own point but nowhere within 100 m stays in the list, below the others. On the demo grid this changes the answer: site 72 has 112 safe days at 0 m on its own point, but none that hold within 100 m until a 5 m mast.
  - The **longest darkness** is the cold soak (IM-2 froze at −173 °C). **Battery needed** (`battery_needed_Wh`) is a full charge minus the lowest level the battery model reaches, worst over the safe landing hours: partial sunlight that keeps charging through a dark spell counts.
- `results.json` (version 4) summarises every site; `sites/<id>.json` gives each top site in full. Both are specified in `docs/ui-data-contract.md`.
- **Battery numbers are provisional** (IoT): 200 W panels, 700 Wh, a 50 W load (estimate) and a 140 Wh floor (assumption) bridge only 11.2 hours without sunlight. The model gives the panels the visible fraction of the Sun whatever its direction, i.e. a sun-tracking array, so survival is an upper bound for fixed panels (see the IM-1 replay). Change the numbers with `--p-load`, `--e-min` and the other battery options of `scripts/score_sites.py`.
- `--earth-margin` makes Earth count only when it clears the skyline by that many degrees (an antenna mask). The default 0 is NASA's rule: any part of Earth's disc visible. Earth in view is not a guaranteed link, but NASA's three Deep Space Network complexes cover the Moon almost continuously, so Earth visibility is the binding constraint.

### Any site, any landing time

```
python scripts/analyze.py --lat -89.778601 --lon -155.72556 --mast 2 --start 2027-03-01T06 --days 14 --coarse data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --out out/analyze/rim.json
```

It runs the engine and SPICE for that one site and writes the same report as `sites/<id>.json`, printing the verdict and the reasons (e.g. "terrain 2.5 km away blocks it (bearing 265 deg ...)"). It takes seconds and needs the maps and kernels, so it runs on a laptop, not in the browser.

### The web app (LunarWindow)

```
python scripts/build_web.py --profiles out/run/profiles   # Moon textures + every preset's results into web/
python scripts/serve.py                                     # http://127.0.0.1:8765/
```

- `web/index.html` is the whole app: a 3D Moon (NASA's LRO colour map, lit with LOLA slopes), a planner map over NASA's sunlight and Earth-visibility maps, one ranking per panel/antenna height, the site's numbers, the **mission player** (the horizon seen from the lander with the Sun and Earth, countdowns to sunset and Earthset, battery), and a side-by-side comparison.
- **Plan your own mission:** set the location, landing hour, mission length, height, battery, panel power, load and Earth margin by hand, or start from a named site (`named_sites.csv`: IM-1 and IM-2 at their real landing hours, the Shackleton rim and crest, the ridge). `scripts/serve.py` runs it through `scripts/analyze.py` (the real engine, SPICE and battery model) in 1–3 s and the player shows the result.
- The page computes no physics: it draws the pipeline's files. Without the server (e.g. a static host), everything but hand-set missions works from `web/data/`.
- **Offline, no server:** `python scripts/build_standalone.py` packs `web/` (page, data, images) into one file, `web_standalone/lunarwindow_standalone.html` (about 7 MB), that opens by double-click. Re-run it after `build_web.py`. Hand-set missions still need `serve.py`.
- `build_web.py` needs NASA's CGI Moon Kit textures in `data/moon/`: `lroc_color_poles_4k.tif` and `ldem_4.tif` from <https://svs.gsfc.nasa.gov/4720>.

**IM-1 replay** (`docs/im1-replay.md`): at Odysseus' real landing site and dates, the tool puts terrain sunset on 2 March 2024 at 14:17 UTC. The lander lost power on 29 February with the Sun still about 5° above the skyline, because it lay tipped with fixed panels facing the wrong way. Terrain didn't end that mission; attitude did.

## Start here (team)

- **What the whole pipeline does:** `docs/landing-site-algorithm.pdf`. It covers Steps 0 to 5, the files passed between steps, and who owns what.
- **Videos (watch these first):** [explainer videos on the horizon engine](https://drive.google.com/drive/folders/1V6i779YKPqB5drJhxOfRTtGKVn8VfF0t?usp=sharing), made with Gemini from our docs and figures. They cover the problem, the geometry, how a ray is walked and why it's fast, the terrain and accuracy studies, and the NASA validation. If a video and the docs disagree on a number, the docs are right.
- **How the horizon engine works:** `docs/horizon-engine/`, chapter by chapter.
- **Results, settings and their evidence:** Parts 4, 6 and 7 below, and Step 5 of the team PDF.
- **Reading Step 1's output (CE 3):**
  - Use `horizon.npy`, `blocker.npy` and `complete.npy`, each shaped [sites, masts, n_az].
  - Always read `n_az` (1,440) and `masts_m` (0, 2, 5, 10 m) from `horizon_meta.json`.
  - Direction j is θ = j · 360 / n_az degrees, from map +x, counterclockwise. Earth sits near θ = 90°.
- **Converting SPICE azimuths (CE 2):** use the direction convention below, and the test that pins it.
- **NASA data isn't in the repo** (it's too large). Download it into `data/` as described in Parts 2, 2b and 6.

The parts below are the order to run things in. "Step N" always means the team pipeline (Steps 0–5 in `docs/landing-site-algorithm.pdf`); this engine is Step 1.

```
horizon/reference.py   tested reference engine (NumPy, one site)
horizon/terrain.py     terrain levels: 20 m terrain near the sites, the 240 m map beyond
horizon/dem.py         loads LOLA south-polar height maps (PDS3 .LBL + .IMG), memory-mapped, optionally cropped
horizon/synthetic.py   test terrains with known answers (cone, ring, crater)
horizon/fast.py        fast Numba engine: many sites in parallel, same answers as the reference
horizon/sites.py       sites.csv (Step 0 -> Steps 1, 4): read with checks, write, demo and random site sets
horizon/__init__.py    engine settings chosen by the convergence study (N_AZ, D_MAX, KAPPA, D_FINE)
scripts/plot_horizon.py  plot the terrain and skyline of one site
scripts/estimate_visibility.py  rough Sun / Earth visibility from a saved skyline
scripts/compare_pgda.py  read NASA's PGDA sunlight / Earth-visibility maps at a site
scripts/validate_pgda.py  compare the engine with NASA's maps pixel by pixel (scatter plot)
scripts/benchmark.py   time the fast engine on real terrain and extrapolate the full grid
scripts/convergence.py  choose range, near-field radius, step factor and azimuth count
scripts/make_demo_sites.py  demo sites.csv around the Shackleton rim, until Step 0's grid exists
scripts/run_horizon.py  batch run: horizon.npy, blocker.npy, complete.npy, horizon_meta.json for Steps 3-4
scripts/make_sky.py   Step 2: Sun and Earth positions per site and hour (SPICE) -> sky.npz
scripts/validate_sky_skyfield.py  independent check of sky.npz with Skyfield
scripts/validate_horizons.py  Step 2 checked against NASA JPL Horizons at every named site (Part 8)
scripts/score_sites.py  Steps 3-4: visibility, safe landing dates, battery, mast, ranking, landing error -> results.json, sites/<id>.json
scripts/events.py     sunrise/sunset, Earthrise/Earthset and DTE windows to the minute; Sun clearance above the skyline
scripts/site_report.py  one site in full for the web app (skyline, tracks, events, verdict, reasons)
scripts/analyze.py    any coordinates and landing time -> the same site report
scripts/battery.py    battery model (IoT)
scripts/make_neighbours.py  points within 100 m of the top sites, for the landing-error check
scripts/sensitivity.py  safe days vs battery size and antenna mask
scripts/named_to_sites.py  named_sites.csv (IM-1, IM-2, Shackleton, ...) -> sites.csv with height and slope over 100 m
scripts/profiles.py   lander presets (mission requirements, never weights) for "Your lander"
scripts/run_profiles.py  Step 4 + landing-error check for every preset
scripts/build_web.py  Moon textures and a copy of every preset's results for the web app
scripts/serve.py      serves web/ and runs hand-set missions (POST /api/mission -> scripts/analyze.py)
scripts/build_standalone.py  web/ as one double-click HTML file for an offline demo (BIT)
web/                  the web app: index.html, assets/ (Moon, NASA PGDA basemaps), data/ (built by build_web.py)
named_sites.csv       notable sites with citations and real landing hours
tests/                 smooth Moon, cone, ring crater, map loading, direction convention, PGDA reader,
                       estimates, fast vs reference, sites.csv checks, convergence, batch run end to end,
                       great-circle geometry, Step 2 joint test with the engine, Steps 3-4 formulas and battery,
                       touchdown rule and ranking, events to the minute, site report, real-terrain regressions
```

## Setup

```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                # expect: 133 passed
```

Without the LOLA maps and SPICE kernels in `data/`, the six real-data checks are skipped (127 passed, 6 skipped): two in `test_fast.py`, the regression tests in `test_real_terrain.py` (Shackleton floor walled in at 19.75–23.52°, rim site dark at 2 m, the crest 103 m away lit 80–92%), `analyze` end to end, and `make_sky` against recorded JPL Horizons answers.

## Part 1: synthetic demo (no download needed)

```
python scripts/plot_horizon.py --synthetic --site shackleton-rim --dmax 60000 --out out/synthetic_rim.png
python scripts/plot_horizon.py --synthetic --site shackleton-floor --dmax 60000 --out out/synthetic_floor.png
```

- **Left panel:** the terrain, with orange dots on the terrain that forms the skyline. The big arc about 32 km away is the Moon's curvature. From a rim 300 m up, a smooth Moon drops out of sight at √(2R·h) ≈ 32 km.
- **Right panel:** the skyline against the Sun's yearly height range (yellow) and Earth's zone (blue).

## Part 2: real LOLA terrain

1. Open <https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/> (the files may be inside an `img` subfolder).
2. Find a **south**-pole height map named like `LDEM_75S_240M` (240 m pixels, about 30 MB), or the coarsest `LDEM_..S_...` file there. Download **both** the `.IMG` and the `.LBL` into `data/`. Skip the 5–30 m versions for now: they are about 1.8 GB each.
3. Open the `.LBL` in a text editor and find `MAP_PROJECTION_TYPE`, `MAP_SCALE`, `SCALING_FACTOR`, `OFFSET` and `UNIT`. The loader checks all of these and stops with a clear error if anything is unexpected. If it stops, send the label to the chat.
4. Run:

```
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-floor --out out/floor.png
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-rim --out out/rim.png
```

### Sanity checks (all must hold)

- **Left panel:** Shackleton is an obvious round crater about 21 km wide, right next to the pole. If the marker isn't on it, the coordinate conversion is wrong. Stop and report.
- **Floor:** the skyline is roughly 15–25° all around, so the Sun never clears it. Shackleton's floor is known to be permanently shadowed, and your engine should agree.
- **Rim:** the skyline is low (near 0° or below) in most directions, so the Sun clears it often.
- **No warning** that rays left the map. The 75°S map (3,812 × 3,812 pixels) reaches 457.3 km from the pole along its axes, so 250 km rays stay on it for every site within 6.8° of the pole.

## Part 2b: compare with NASA's published maps

NASA's PGDA archive publishes average sunlight and Earth-visibility maps of the south pole, averaged hourly over 18.6 years. Download these two files (60 m pixels, 85–90°S) into `data/`:

- <https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF> (Sun)
- <https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF> (Earth)

Then read both at your rim site:

```
python scripts/compare_pgda.py data/AVGVISIB_85S_060M_201608.TIF --lat -89.778601 --lon -155.72556
python scripts/compare_pgda.py data/AVGVISIB_85S_060M_201608_EARTH.TIF --lat -89.778601 --lon -155.72556
```

The script uses the map's own projection, checks that it agrees with ours to within 1 m, applies the map's scale and offset, and prints the value at the site plus its 5×5 neighbourhood (±120 m).

**Our rough estimates to compare against:**

```
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-rim --save out/rim.npz
python scripts/estimate_visibility.py out/rim.npz
```

On the 240 m map alone: Sun **86.6%**, Earth **56.3%**. The 240 m map smooths the local crest into the site, so it looks lit; with 20 m terrain near the site (Part 6) the site is dark (0.3% Sun, 36.2% Earth) and the crest 103 m away gets 85.9% and 56.3%. Don't compare with "NASA's value at the site": a site from the 240 m grid sits exactly on a corner of four 60 m pixels (Sun 0%, 6%, 47%, 56% here), so the script warns and prints all four. Compare pixel by pixel instead (Part 7).

## The direction convention (share with CE 2)

- θ is measured **from the map's +x axis, counterclockwise**, 0–360°.
- Longitude 0 is map **up** (θ = 90°). Longitude 90°E is map **right** (θ = 0°).
- This is pinned by `test_longitude_0_is_map_up_and_90E_is_map_right`. The Sun and Earth directions from SPICE must be converted to this θ (study guide section 3.10).

The yellow Sun band and blue Earth zone in the plot are rough guides. Exact Sun and Earth positions come from SPICE (CE 2).

## Part 3: the fast engine

`horizon/fast.py` runs many sites in parallel with Numba and gives the same answers as the reference (H within 1e-6°, D and the completeness flag identical; `tests/test_fast.py`). Time it on real terrain:

```
python scripts/benchmark.py data/ldem_75s_240m.lbl
```

On 12 threads: about 2 ms per site at 1,440 azimuths and 250 km on the 240 m map, over 100 times the reference.

## Part 4: convergence (choose the settings)

```
python scripts/convergence.py data/ldem_75s_240m.lbl
```

Runs the rim site plus 500 random sites within 5° of the pole over every combination of range (100–300 km), step factor (0.002–0.00025) and azimuth count (360–11,520). The reference is the finest value of each: 300 km, κ 0.00025, 11,520 azimuths. 300 km rays only stay on the 240 m map for sites within 5°, hence the default `--within 5`. With `--fine` it studies the 20 m near field instead of the range (Part 6).

The rule: **every site's skyline within 0.02° of the reference in 99% of its directions**. Missing terrain shifts whole sectors of a site and fails it; single directions at sharp kinks converge slowly but don't change what planners see. Azimuth error is measured *between* rays, where Steps 3–4 interpolate. The study also prints how much the chosen settings move each site's Sun and Earth visibility. That's reported, not part of the rule: near 0% or 100% visibility, a 0.002° skyline change can move it 0.3 points.

Result: **1,440 azimuths, 250 km, κ = 0.002**, stored in `horizon/__init__.py`; every script defaults to them. 200 km is not enough: distant massifs leave the worst site 0.68° off in 99% of its directions. 250 km and 300 km agree exactly. Takes about 10 minutes; re-run it when the terrain changes.

## Part 5: batch run (files for Steps 3–4)

```
python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --out out/demo/sites.csv
python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --fine data/ldem_875s_20m.lbl --out out/demo
```

The demo grid is 20 × 20 sites, 480 m apart, around the rim site (site 210). `run_horizon.py` writes `horizon.npy` and `blocker.npy` (float32) and `complete.npy` (bool), each [sites, masts, n_az], plus `horizon_meta.json`. Read `n_az` and `masts_m` from the meta file, never assume them. Once Step 0 delivers the real `sites.csv`, run the same command on it; `horizon/sites.py` checks it first (missing columns, duplicate ids, x/y that disagree with lat/lon).

## Part 6: 20 m terrain near the sites

Download `ldem_875s_20m.img` and `.lbl` (115 MB, 87.5–90°S, ±75.8 km around the pole) from the same PDS folder into `data/`. Then:

```
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --site shackleton-rim --save out/rim_fine.npz --out out/rim_fine.png
python scripts/estimate_visibility.py out/rim_fine.npz
python scripts/convergence.py data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --within 0.43 --sites 150
```

Each ray samples the 20 m map out to `D_FINE` = 40 km from the site and the 240 m map beyond. The loader memory-maps the image and reads only the crop the sites need, so the 1.85 GB maps never load whole. If the 20 m map doesn't reach 40 km around a site, the engine stops with an error rather than quietly using coarser terrain. Expect the rim site to come out dark at a 2 m mast (0.3% Sun): a crest 103 m away and 9.3 m higher blocks it. At a 10 m mast it gets 80.4%.

- The 87.5°S map serves sites within about 36 km of the pole. For every site within 6°, download `ldem_80s_20m` (1.85 GB, ±304 km).
- The 240 m map is the 12 × 12 block mean of the 20 m map (1.6 m RMS), so the two join without offsets.
- No max-pyramid. Measured on real terrain, a pyramid sampled bilinearly still misses peaks and pushes 3% of directions more than 0.02° too high; direct 20 m sampling is simpler and more accurate.

## Part 7: validate against NASA, pixel by pixel

```
python scripts/validate_pgda.py data/ldem_75s_240m.lbl data/ldem_875s_20m.lbl data/AVGVISIB_85S_060M_201608.TIF data/AVGVISIB_85S_060M_201608_EARTH.TIF
python scripts/validate_pgda.py ... --lat -89.47485 --lon -137.44314 --out out/validate_pgda_ridge.png
```

Runs the engine at the centre of each of the 10 × 10 NASA 60 m pixels around a site (a 600 m square), with 20 m terrain near each pixel and the 240 m map beyond. It then computes Sun and Earth visibility exactly as NASA's maps define them, with the pipeline's own sky (SPICE, every hour for 18.6 years) and Step 3 formulas: the average visible fraction of the Sun's disc, and the share of hours with any part of Earth's disc in view. NASA's product page says its maps are "averaged over hourly timesteps spanning 18.6 years" and counts Earth as visible "if any part of its disc is not obscured".

Two sites: the Shackleton rim site, and the brightest NASA pixel within 30 km of the pole away from it (88.4% Sun at 89.475°S, 137.44°W, on the Shackleton–de Gerlache ridge). Correlation / average difference (ours − NASA, points) / share within 10 points:

| Mast | Rim: Sun | Rim: Earth | Ridge: Sun | Ridge: Earth |
|---|---|---|---|---|
| 0 m | 0.49 / −11.3 / 64% | 0.80 / −5.8 / 78% | 0.57 / −14.2 / 37% | 0.81 / −5.0 / 78% |
| **2 m** | **0.92 / +0.1 / 94%** | **0.85 / +0.6 / 89%** | **0.83 / +1.9 / 86%** | **0.90 / +2.2 / 92%** |
| 5 m | 0.82 / +7.6 / 70% | 0.89 / +4.8 / 80% | 0.74 / +13.6 / 43% | 0.90 / +5.4 / 73% |
| 10 m | 0.57 / +14.7 / 49% | 0.86 / +8.6 / 67% | 0.56 / +25.1 / 12% | 0.85 / +7.4 / 63% |

- At 2 m our Sun and Earth match NASA's maps pixel by pixel at both sites, within about 2 points on average. Scatter plots: `out/validate_pgda.png`, `out/validate_pgda_ridge.png`.
- 2 m is the best fit at both sites independently. NASA doesn't state its observer height, so that's an observed fit, not a fact about their setup.
- Before Nov 12 this used rough estimates (a yearly sine for the Sun, a libration band for Earth): Sun 0.92 / +0.4, Earth 0.85 / −3.8 at the rim. With the real SPICE sky the Earth bias drops from −3.8 to +0.6 points.
- Each block's 100 pixels lie within 600 m and share the distant skyline, so they aren't 100 independent checks. The two sites, 9.8 km apart, are.

## Part 8: validate the Sun and Earth against NASA JPL Horizons

```
python scripts/validate_horizons.py --sites named_sites.csv --out out/validate_horizons.json
```

[JPL Horizons](https://ssd.jpl.nasa.gov/horizons/) is the ephemeris service listed in the challenge's Resources tab. For every named site (IM-1, IM-2, the Shackleton rim, the crest 103 m away, the Shackleton–de Gerlache ridge, Apollo 11), the script asks the Horizons API where the Sun and Earth are, seen from that point on the Moon's surface:
- at ten hours spread over 2026–2030;
- and at the real landing hour of IM-1 (2024-02-22 23 UTC) and IM-2 (2025-03-06 17 UTC).

Horizons settings:
- an observer table centred on a surface point (`CENTER = 'coord@301'`), geodetic on the Moon's mean-Earth frame (the frame LOLA uses);
- apparent azimuth and elevation, with no refraction (`APPARENT = 'AIRLESS'`);
- times in UT.

The same hours go through `make_sky()`, the code the pipeline uses. It fails if any difference exceeds 0.01°.

Result (Nov 13, 2026): **124 positions, every one within 0.0003° of Horizons.**
- Elevation: worst 0.000013° (Sun) and 0.000035° (Earth).
- Azimuth: worst 0.000036° for Earth. For the Sun the worst is 0.000274°, at Apollo 11 with the Sun 89.4° up; that close to the zenith, azimuth is nearly undefined (it is a 0.000003° shift on the sky). Everywhere else it is within about 0.00001°.

For scale, the Sun's radius is 0.27°. Two independent sources, Skyfield (`validate_sky_skyfield.py`, 0.00032° worst) and NASA's own JPL Horizons, agree with our SPICE sky. That leaves terrain as the only real source of error, and the convergence study (Part 4) and NASA's PGDA maps (Part 7) check that.

## References

- Smith, D. E., et al. (2010). The Lunar Orbiter Laser Altimeter investigation on the Lunar Reconnaissance Orbiter mission. *Space Science Reviews*, 150, 209–241. (LOLA)
- LOLA gridded data records (LDEM_75S_240M, LDEM_875S_20M), NASA PDS Geosciences Node: <https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/>
- Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. *Icarus*, 211, 1066–1081. (the horizon method and NASA's PGDA maps)
- NASA PGDA, Lunar Polar Illumination (product 69): <https://pgda.gsfc.nasa.gov/products/69>
- Acton, C. H. (1996). Ancillary data services of NASA's Navigation and Ancillary Information Facility. *Planetary and Space Science*, 44(1), 65–70. (SPICE)
- Folkner, W. M., Williams, J. G., & Boggs, D. H. (2008). The Planetary and Lunar Ephemeris DE 421. *IPN Progress Report* 42-178. (DE421 and the Moon's orientation)
- Barker, M. K., et al. (2021). Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions. *Planetary and Space Science*, 203, 105119. https://doi.org/10.1016/j.pss.2020.105119 (why 20 m terrain near a site matters)
- NASA JPL Solar System Dynamics, Horizons System (API: <https://ssd.jpl.nasa.gov/api/horizons.api>): <https://ssd.jpl.nasa.gov/horizons/> (independent check of every Sun and Earth position, Part 8)
- NASA, Artemis overview for the Space Apps Challenge (landing site requirements: within 6° of the pole, slope under 10°, direct-to-Earth communication, land within 100 m): <https://ntrs.nasa.gov/api/citations/20250009323/downloads/ArtemisOverview2025IntSPAPPSChallenge.pdf>
- Software: [SpiceyPy](https://github.com/AndrewAnnex/SpiceyPy), [NumPy](https://numpy.org), [Numba](https://numba.pydata.org), [rasterio](https://rasterio.readthedocs.io), [pyproj](https://pyproj4.github.io/pyproj), [Skyfield](https://rhodesmill.org/skyfield) (independent sky check).
