# Horizon engine

Part of our CLPS Lunar Mission Browser (NASA Space Apps 2026). This engine computes a site's **skyline**: for every direction θ, the horizon elevation H(θ) and the distance to the terrain that blocks the sky.

```
horizon/reference.py   tested reference engine (NumPy, one site)
horizon/dem.py         loads LOLA south-polar height maps (PDS3 .LBL + .IMG), lat/lon <-> grid
horizon/synthetic.py   test terrains with known answers (cone, ring, crater)
horizon/fast.py        fast Numba engine: many sites in parallel, same answers as the reference
horizon/sites.py       sites.csv (Step 0 -> Steps 1, 4): read with checks, write, demo and random site sets
horizon/__init__.py    engine settings chosen by the convergence study (N_AZ, D_MAX, KAPPA)
scripts/plot_horizon.py  plot the terrain and skyline of one site
scripts/estimate_visibility.py  rough Sun / Earth visibility from a saved skyline
scripts/compare_pgda.py  read NASA's PGDA sunlight / Earth-visibility maps at a site
scripts/benchmark.py   time the fast engine on real terrain and extrapolate the full grid
scripts/convergence.py  choose range, step factor and azimuth count (skyline within 0.02 deg)
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
python -m pytest -q                # expect: 25 passed
```

Without `data/ldem_75s_240m.lbl`, the real-terrain check in `test_fast.py` is skipped (24 passed, 1 skipped).

## Step 1: synthetic demo (no download needed)

```
python scripts/plot_horizon.py --synthetic --site shackleton-rim --dmax 60000 --out out/synthetic_rim.png
python scripts/plot_horizon.py --synthetic --site shackleton-floor --dmax 60000 --out out/synthetic_floor.png
```

- **Left panel:** the terrain, with orange dots on the terrain that forms the skyline. The big arc about 32 km away is the Moon's curvature. From a rim 300 m up, a smooth Moon drops out of sight at √(2R·h) ≈ 32 km.
- **Right panel:** the skyline against the Sun's yearly height range (yellow) and Earth's zone (blue).

## Step 2: real LOLA terrain

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

## Step 2b: compare with NASA's published maps

NASA's PGDA archive publishes average sunlight and Earth-visibility maps of the south pole, averaged hourly over 18.6 years. Download these two files (60 m pixels, 85–90°S) into `data/`:

- <https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF> (Sun)
- <https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF> (Earth)

Then read both at your rim site:

```
python scripts/compare_pgda.py data/AVGVISIB_85S_060M_201608.TIF --lat -89.779 --lon -155.73
python scripts/compare_pgda.py data/AVGVISIB_85S_060M_201608_EARTH.TIF --lat -89.779 --lon -155.73
```

The script uses the map's own projection, checks that it agrees with ours to within 1 m, applies the map's scale and offset, and prints the value at the site plus its 5×5 neighbourhood (±120 m).

**Our rough estimates to compare against:**

```
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-rim --save out/rim.npz
python scripts/estimate_visibility.py out/rim.npz
```

- Sun: **86.6%** of the year.
- Earth: **56.3%** of the time.

Expect small differences: our Sun model is simplified, our terrain is coarser (240 m), and NASA averages over 18.6 years.

## The direction convention (share with CE 2)

- θ is measured **from the map's +x axis, counterclockwise**, 0–360°.
- Longitude 0 is map **up** (θ = 90°). Longitude 90°E is map **right** (θ = 0°).
- This is pinned by `test_longitude_0_is_map_up_and_90E_is_map_right`. The Sun and Earth directions from SPICE must be converted to this θ (study guide section 3.10).

The yellow Sun band and blue Earth zone in the plot are rough guides. Exact Sun and Earth positions come from SPICE (CE 2).

## Step 3 (week 2): the fast engine

`horizon/fast.py` runs many sites in parallel with Numba and gives the same answers as the reference (H within 1e-6°, D and the completeness flag identical; `tests/test_fast.py`). Time it on real terrain:

```
python scripts/benchmark.py data/ldem_75s_240m.lbl
```

On 12 threads: about 8 ms per site at 5,760 azimuths and 250 km, over 100 times the reference.

## Step 4: convergence (choose the settings)

```
python scripts/convergence.py data/ldem_75s_240m.lbl
```

Runs the rim site plus 500 random sites within 6° of the pole over every combination of range (100–250 km), step factor (0.002–0.0005) and azimuth count (360–11,520), and picks the cheapest whose skyline stays within 0.02° of the finest in every direction. Azimuth error is measured *between* rays, where Steps 3–4 interpolate, against a reference twice as fine as any candidate. Result on the 240 m map: **5,760 azimuths, 250 km, κ = 0.002** (worst error 0.012°), stored in `horizon/__init__.py`; every script defaults to them. 200 km is not enough: distant massifs still change skylines by up to 0.8°. Takes about 2 minutes; re-run it when the terrain changes.

## Step 5: batch run (files for Steps 3–4)

```
python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --out out/demo/sites.csv
python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --out out/demo
```

The demo grid is 20 × 20 sites, 480 m apart, around the rim site (site 210). `run_horizon.py` writes `horizon.npy` and `blocker.npy` (float32) and `complete.npy` (bool), each [sites, masts, n_az], plus `horizon_meta.json`. Read `n_az` and `masts_m` from the meta file, never assume them. Once Step 0 delivers the real `sites.csv`, run the same command on it; `horizon/sites.py` checks it first (missing columns, duplicate ids, x/y that disagree with lat/lon).
