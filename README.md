# Horizon engine

Part of our CLPS Lunar Mission Browser (NASA Space Apps 2026). This engine computes a site's **skyline**: for every direction θ, the horizon elevation H(θ) and the distance to the terrain that blocks the sky.

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
tests/                 smooth Moon, cone, ring crater, map loading, direction convention, PGDA reader,
                       estimates, fast vs reference, sites.csv checks, convergence, batch run end to end
```

## Setup

```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                # expect: 34 passed
```

Without the LOLA maps in `data/`, the two real-terrain checks in `test_fast.py` are skipped (32 passed, 2 skipped).

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
- **No warning** that rays left the map. The 75°S map reaches about 455 km from the pole.

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
```

Runs the engine at the centre of each of the 10 × 10 NASA pixels around the rim site (a 600 m square), with 20 m terrain near each pixel and the 240 m map beyond, and compares our Sun and Earth estimates with NASA's values. Expect:

| Mast | Sun: correlation / average difference / within 10 points | Earth: correlation / average difference |
|---|---|---|
| 0 m | 0.50 / −11.0 / 64% | 0.78 / −10.0 |
| **2 m** | **0.92 / +0.4 / 93%** | 0.85 / −3.8 |
| 5 m | 0.82 / +7.9 / 70% | 0.86 / +0.8 |
| 10 m | 0.57 / +15.1 / 48% | 0.84 / +5.5 |

At 2 m our Sun estimate matches NASA's map pixel by pixel (scatter plot in `out/validate_pgda.png`). NASA doesn't state its observer height, so that is an observed best fit, not a fact about their setup. Earth matches less well because our Earth estimate is crude; SPICE (Step 2) will replace it.
