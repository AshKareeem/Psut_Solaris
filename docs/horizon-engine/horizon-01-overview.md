# How our horizon engine works

## Part 1: Chapters 1–2 (the judge script and the big picture)

Snapshot: commit `7e50c80`. `file:line` refers to that commit. Every number comes from the project files (`02_CLAUDE.md`, `03_code.md`, `04_data.json`, `06_README.md`, the team PDF) or from a calculation shown here.

---

# Chapter 1. The 60-second version

## 1.1 The script (first draft, about 160 words)

Three beats: **why it matters**, **what the engine does**, **why you should believe it**. Each takes about 20 seconds.

> **[Why]** At the Moon's south pole the Sun stays within about 1.5° of level, and Earth hangs in one direction, bobbing about 6.7°. A few degrees of terrain decide whether a lander gets power and a link home. IM-2 landed on its side in a shadowed crater and stopped within 13 hours.
>
> **[What]** Our engine computes each site's skyline. In 1,440 directions it walks 250 km over NASA terrain, 20 m pixels near the site and 240 m beyond, and keeps the steepest angle, curvature included. It runs once per site and mast height; after that, the Sun or Earth at any hour is a lookup.
>
> **[Proof]** Four hundred sites at four mast heights take 10 seconds. At 100 NASA pixels on Shackleton's rim, our sunlight estimate matches NASA's map with correlation 0.92. And it sees what coarse maps hide: one rim site sits below a crest 103 m away. From a 2 m mast it's almost always dark; a 10 m mast restores 80% sunlight.

## 1.2 The 15-second version (40 words)

> At the lunar south pole the Sun stays within 1.5° of level, so a few degrees of terrain decide power and Earth contact. Our engine computes each site's skyline once from NASA terrain; after that, any hour is a lookup.

We refine both at the end, once you know every part well enough to cut it safely.

## 1.3 Every number in the script, and where it comes from

If a judge asks "where does that number come from?", this is your answer.

| Claim | Number | Source |
|---|---|---|
| Sun's height range at the pole | ±1.54° (said as "about 1.5°") | `02_CLAUDE.md` §2; `scripts/estimate_visibility.py:24` |
| Earth's bob (libration) | ±6.7° | `02_CLAUDE.md` §2; `scripts/estimate_visibility.py:26` |
| IM-2 | on its side in a ~20 m crater, in shadow; operations ended less than 13 h after landing | `02_CLAUDE.md` §2 |
| Directions | 1,440, 0.25° apart | `horizon/__init__.py:6` |
| Range | 250 km | `horizon/__init__.py:7` |
| Terrain | 20 m pixels within 40 km, 240 m beyond | `horizon/__init__.py:9`; README Part 6 |
| Speed | 400 sites × 4 masts in 10.3 s on 12 threads (demo near the pole) | `02_CLAUDE.md` §8 |
| NASA match | Sun: correlation 0.92, average difference +0.4 points, 93% of pixels within 10 points (2 m observer, 100 pixels of 60 m) | `02_CLAUDE.md` §8; README Part 7 |
| The crest | +9.25 m, 103.0 m from the site, at θ = 29.1° | `04_data.json` `readme.terrain_near`; `02_CLAUDE.md` §8 |
| Rim site Sun | 86.6% (240 m map) → 0.3% (20 m terrain, 2 m mast) → 80.4% (10 m mast) | `04_data.json` `skylines.visibility`; `02_CLAUDE.md` §8 |

## 1.4 Where a judge will push on this script

Three sentences in the script are true but compressed. Know the full answer before you say them.

1. **"Correlation 0.92"**
   - It's one site so far. The 100 pixels lie in a 600 m square and share the same distant skyline, so they are not 100 independent checks.
   - 2 m was the best of the observer heights tried; NASA doesn't state theirs.
   - The Sun model is a rough yearly estimate, not SPICE.
   - Honest answer: "One area so far; more sites once the larger 20 m map is in." (`02_CLAUDE.md` §8, "What it does not prove yet".)
2. **"10 seconds"**
   - That's the demo: 400 sites near the pole, on 20 m + 240 m terrain, 12 threads.
   - The full grid (10,000 sites × 4 masts) is an estimate, about 5 minutes. It hasn't run yet: it waits for Step 0's grid and the 1.85 GB 20 m map (`02_CLAUDE.md` §6, definition of done).
3. **"Curvature included"**
   - The angle formula is exact on a sphere. The engine walks straight lines on the *map* and treats map distance as surface distance.
   - Measured error: 0.003° at the rim site, 0.048° for sites 5–6° from the pole.
   - A fix is planned before the full-grid run (`02_CLAUDE.md` §9, "Great circles"). Chapter 3 covers it.

## Try it yourself (Chapter 1)

Write each prediction down *before* you run the command.

**1. The test count.**

```
python -m pytest -q
```

- Predict:
  - (a) the total;
  - (b) how many of those tests live in `tests/test_fast.py`;
  - (c) which two would skip if `data/` had no LOLA maps.
- Answers:
  - (a) 34 passed (README, Setup).
  - (b) 9.
  - (c) the two real-terrain checks: `test_fast_matches_reference_on_lola` (`tests/test_fast.py:100–104`) and `test_fast_matches_reference_on_lola_20m_and_240m` (`:107–112`). Without the maps it reads 32 passed, 2 skipped.

**2. The rim story in three runs.** These are the commands from README Parts 2b and 6, plus `--mast 10` (a real flag, `scripts/plot_horizon.py:111`).

```
python scripts/plot_horizon.py data/ldem_75s_240m.lbl --site shackleton-rim --save out/rim.npz
python scripts/estimate_visibility.py out/rim.npz

python scripts/plot_horizon.py data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --site shackleton-rim --save out/rim_fine.npz --out out/rim_fine.png
python scripts/estimate_visibility.py out/rim_fine.npz

python scripts/plot_horizon.py data/ldem_75s_240m.lbl --fine data/ldem_875s_20m.lbl --site shackleton-rim --mast 10 --save out/rim_fine_m10.npz --out out/rim_fine_m10.png
python scripts/estimate_visibility.py out/rim_fine_m10.npz
```

- Predict the Sun and Earth percentages for each run. Read the first number on each line; the "no tilt" one comes second.
- Then answer: why is the Earth number the same in the first and third runs?
- Answers:
  - Sun 86.6%, 0.3%, 80.4%. Earth 56.3%, 36.2%, 56.3%.
  - The Earth estimate uses the highest skyline in θ = 82°–98° (`estimate_visibility.py:46`). In both runs that is −0.57° at θ = 86°, set by the same terrain about 127 km away: D = 127,179 m and 127,256 m in `04_data.json`.
  - At 10 m the near crest drops below that far skyline. So toward Earth, the 20 m terrain changes nothing.

---

# Chapter 2. The big picture

## 2.1 What Step 1 computes

**Inputs:** a site (map position x, y in metres), a mast height m, and the terrain.

**Output:** for every direction θ, three numbers.

| Output | Meaning | Unit |
|---|---|---|
| **H** | Horizon elevation: the steepest angle up to any terrain in that direction, measured from the local horizontal at the mast top | degrees |
| **D** | Blocker distance: how far along the ray the terrain that sets H lies | metres |
| **complete** | True if the ray still had terrain under it at the full range (250 km) | bool |

One direction, side view (heights exaggerated):

```
                                                     B   <- sets H: steepest sight line
                                             . ' '  /\
                                     . ' '         /  \
                             . ' '        A       /    \
                     . ' '               /\      /      \
  mast top   o . ' '   ) H              /  \    /        \
             |  ------------- local horizontal --------------
  site     __|_________________________/    \__/          \___
             |<------------------------- D ---------------->|
```

- Peak A is nearer, but its sight line is below B's.
- B is farther and higher, and its angle is larger. So B sets H, and D is the distance to B.
- "Local horizontal" is the plane perpendicular to the Moon's radius through the observer (`reference.py:48`: "height above the observer's level").
- CE 2's SPICE elevations must be measured from the same plane, or every comparison in Step 3 is biased (`02_CLAUDE.md` §5).

All directions, top view:

```
                    θ = 90°  (map up = toward longitude 0 = toward Earth)
                         ^
                         |
         θ = 180° <----- o -----> θ = 0°  (map +x = toward longitude 90°E)
                       site
                         |
                         v
                    θ = 270°

   1,440 rays, 0.25° apart, each walking out to 250 km
```

θ is measured from map +x, counterclockwise (`fast.py:36`). Chapter 3 explains why compass bearings fail at the pole.

**The sign of H matters, and it's never clamped.**

- Positive H: terrain sticks up above level in that direction.
- Negative H: you can see below level. That happens when you're on high ground, or simply because the Moon curves away. A perfectly smooth Moon seen from 2 m gives −0.087° (`tests/test_reference.py:25–30`).
- If H were clamped to 0, the Sun at −0.05° would be called hidden when it's visible.

**A taller mast lowers H in every direction.** Here's the proof, from the tangent the engine computes for every sample (`fast.py:76`):

```
t = (r_pt·cos φ − r_obs) / (r_pt·sin φ)        r_obs = R + ground + mast   (fast.py:38)
```

- Raising the mast raises r_obs.
- That lowers the top line of every sample's fraction; the bottom line doesn't change.
- So every sample's angle falls, and their maximum H falls too.
- `tests/test_run_horizon.py:31` checks exactly this: mast 0 m gives a higher skyline than mast 2 m at every site and direction.

**Why masts at all?** Step 4 recommends the lowest mast that meets the targets (differentiator 4, `02_CLAUDE.md` §3). Also, the Sun check uses panel height and the Earth check uses antenna height (`run_horizon.py:31`). The masts are 0, 2, 5 and 10 m.

### The rim site's three skylines

From `04_data.json` and `02_CLAUDE.md` §8. The D ranges come from the 1°-sampled data (360 of the 1,440 directions). Sun and Earth come from the rough yearly model, not SPICE.

| Terrain | Mast | Skyline H | Blockers D | Sun | Earth |
|---|---|---|---|---|---|
| 240 m only | 2 m | −2.66° to +1.03° | 2.9 km to 197.8 km | 86.6% | 56.3% |
| 20 m + 240 m | 2 m | +1.56° to +5.84° | 30 m to 110 m | 0.3% | 36.2% |
| 20 m + 240 m | 10 m | −2.51° to +1.06° | 70 m to 197.9 km | 80.4% | 56.3% |

**What D tells you that H doesn't.**

- **20 m terrain, 2 m mast:** every blocker is 30–110 m away. The skyline is *local*.
  - Moving 12 m changes Earth visibility by about 5 points (`02_CLAUDE.md` §8).
  - So landing error and mast height matter enormously here.
- **240 m map only:** the blockers are kilometres to ~200 km away. A *far* skyline barely changes if you land 100 m off.
- **Same answer at θ = 90°.** The 240 m map with a 2 m mast gives H = −0.70° (D = 127,688 m). 20 m terrain with a 10 m mast also gives −0.70° (D = 127,511 m). Same distant massif.
  - Why the two observer heights don't matter there: they differ by (1,729.25 + 10) − (1,734.5 + 2) = 2.75 m.
  - At 127.5 km that shifts the angle by about 2.75 / 127,500 rad = 0.0012°, invisible at two decimals.
- **D is quantised to the step schedule.**
  - Near the site on 20 m terrain the steps are 10 m, so blockers read 30, 40, … 110 m.
  - On the 240 m-only run the steps are 120 m out to 60 km, so 20,880 m = 174 × 120 m and 2,880 m = 24 × 120 m.
  - Chapter 4 derives the schedule.

**The engine's interface** (`fast.py:19–24`):

```python
H, D, complete = horizon_profiles_fast(terrain, xs, ys, mast, d_max, n_az, kappa)
#  H [sites, n_az] deg     D [sites, n_az] m     complete [sites, n_az] bool
```

- It handles one mast per call, for many sites at once.
- `n_az` and `kappa` are required arguments since `7e50c80`. Callers pass the settings from `horizon/__init__.py`.

## 2.2 Why compute it once, offline, and then only look things up

**What changes with time, and what doesn't:**

| Thing | Changes with time? |
|---|---|
| Terrain, site, mast | No |
| Sun and Earth directions (az, el) | Yes, every hour |

H depends only on the things in the first row. So compute it once. Then any hour is a comparison: look up H at the Sun's azimuth, and compare it with the Sun's elevation.

**The cost argument** (team PDF, Step 1):

```
Direct:  2 bodies (Sun, Earth) × 24 h × 365 days = 17,520 terrain walks per site per year
Horizon: 1,440 terrain walks per site, once
Ratio:   17,520 / 1,440 = 12.2   -> about 12× less work for one year
```

- The gap grows with every extra year and every date range a user tries.
- That is the challenge's core demand: "compare landing sites and dates **quickly**" (`02_CLAUDE.md` §2).
- The heavy work is done before anyone opens the app.

**What the lookup is** (Step 3, `02_CLAUDE.md` §5). It's a few array reads and one interpolation between the two nearest directions (0.25° apart):

```
fraction of Sun visible:  s(t) = clamp((el☉ − H(az☉) + r☉) / (2·r☉), 0, 1)     r☉ = 0.27°
Earth visible:            e(t) = el⊕ + r⊕ > H(az⊕)                               r⊕ = 0.95°
```

**Worked lookup.** Take the rim site at θ = 90°, with the Sun hypothetically at elevation +1.0° in that direction. The H values come from `04_data.json`.

```
2 m mast,  H = +3.33°:  s = clamp((1.00 − 3.33 + 0.27) / 0.54, 0, 1) = clamp(−3.81) = 0   -> dark
10 m mast, H = −0.70°:  s = clamp((1.00 + 0.70 + 0.27) / 0.54, 0, 1) = clamp(+3.65) = 1   -> fully lit
```

The same Sun and the same site, and the answer depends on 8 m of mast. That's the whole product in one line.

## 2.3 Where Step 1 sits in the pipeline

```
 NASA data              team steps (owner)                                   files
 ─────────              ──────────────────                                   ─────
 LOLA maps ──┬──► Step 0  terrain, slope, candidate sites (IoT) ─────────►  sites.csv
             │                                                                 │
             └──────────────────────┐                                          │
                                    ▼                                          ▼
                        Step 1  horizon engine (Ash) ──────────────►  horizon.npy, blocker.npy,
                                                                     complete.npy, horizon_meta.json
                                                                               │
 SPICE ─────────► Step 2  Sun & Earth az/el per site per hour (CE 2) ──►  sky.npz
                                                                               │
                        Step 3  visibility each hour (CE 3) ◄──────────────────┘
                                    │  visibility.npz: s(t), e(t), b(t)
                                    ▼
                        Step 4  score, battery, landing error, mast, best dates (CE 3 + IoT)
                                    │  results.json
                                    ▼
                        Web app (BIT)

 Step 5 validation: tests (Ash) + NASA map comparison (Business), checking Steps 1 and 4

 Offline, once:            Steps 0–1
 Per date range (cheap):   Steps 2–3 (and 4)
```

Sources: team PDF Figure 1 and `02_CLAUDE.md` §4–5.

**What Step 1 reads:**

| Input | Read by | Notes |
|---|---|---|
| `sites.csv` | `horizon/sites.py:16–35` (`read_sites`) | Uses `id`, `x`, `y`. Fails fast on missing columns, duplicate ids, or x/y that disagree with lat/lon by over 1 m. The `height` column is for display only. |
| LOLA maps (`.LBL` + `.IMG`) | `horizon/dem.py:51–93` | The 240 m map whole; the 20 m map cropped to sites ± 40 km (`run_horizon.py:65`) |
| Settings | `horizon/__init__.py:6–9` | N_AZ = 1440, D_MAX = 250 km, KAPPA = 0.002, D_FINE = 40 km |

**The ground height comes from the finest terrain, not from `sites.csv`** (`fast.py:32`). At the rim site that's 1,729.25 m on the 20 m map, while the 240 m map says 1,734.5 m (`04_data.json` `site`). Those 5.25 m are the crest-and-dip story in miniature.

**Open item:** the PDF and `02_CLAUDE.md` §5 still list `dem.npy` as Step 1's input. The code reads the `.LBL` directly (`run_horizon.py:63–66`). It's pending agreement with Step 0 (`02_CLAUDE.md` §9).

## 2.4 The four output files

`scripts/run_horizon.py` writes them:

- `:34–38` computes all masts;
- `:41–47` writes the arrays;
- `:70–84` builds the metadata.

| File | Type and shape | Contents | Used by |
|---|---|---|---|
| `horizon.npy` | float32 [sites, masts, n_az] | H, degrees | Step 3 (CE 3): compares Sun and Earth elevations against it |
| `blocker.npy` | float32 [sites, masts, n_az] | D, metres | Step 3 and the web app: "why" explanations, near vs far blockers |
| `complete.npy` | bool [sites, masts, n_az] | the ray has terrain at d_max | Step 3: the trust flag |
| `horizon_meta.json` | JSON | the settings and conventions needed to read the arrays | everyone who reads the arrays |

**How the mast axis gets into the middle** (`run_horizon.py:36–38`). This is a NumPy idiom you'll see again:

```python
runs = [horizon_profiles_fast(..., m, ...) for m in masts]
# runs = [(H_0m, D_0m, ok_0m), (H_2m, D_2m, ok_2m), ...]    each array [sites, n_az]
H, D, ok = (np.stack(a, axis=1) for a in zip(*runs))
# zip(*runs)  regroups by quantity: (H_0m, H_2m, H_5m, H_10m), (D_0m, ...), (ok_0m, ...)
# np.stack(a, axis=1) inserts a new axis at position 1:  [sites, n_az] x 4  ->  [sites, 4, n_az]
```

**Rules for anyone reading the files.** Send these to CE 3.

1. **Site i is row i of `sites.csv`** (`run_horizon.py:8`).
2. **Direction j is θ_j = j · 360 / n_az degrees** from map +x, counterclockwise (`run_horizon.py:8`).
   - With n_az = 1,440: j = 360 is θ = 90°, toward longitude 0 and Earth.
3. **Read `n_az` and `masts_m` from the metadata. Never hard-code them** (`run_horizon.py:7`). The old team PDF said 360 directions; it's 1,440 now.
4. **Interpolate H between neighbouring directions, wrapping at 360°.**
   - The convergence study measured the error exactly that way, *between* rays (`scripts/convergence.py:49–54`).
   - Snapping to the nearest ray is a different (worse) method, and the error budget wasn't checked for it.
5. **Units are degrees and metres.**

**The metadata** (the demo run, from `04_data.json` `example_horizon_meta`):

```json
{
  "n_sites": 400, "n_az": 1440,
  "azimuth": "theta_j = j * 360 / n_az deg, from map +x (toward 90E), counterclockwise; 90 deg = toward lon 0",
  "masts_m": [0.0, 2.0, 5.0, 10.0], "d_max_m": 250000.0, "kappa": 0.002, "R_m": 1737400.0,
  "dem_files": ["ldem_875s_20m.lbl", "ldem_75s_240m.lbl"], "dem_starts_m": [0.0, 40000.0],
  "sites_file": "sites.csv"
}
```

`dem_files` lists the finest first. `dem_starts_m` says where each one starts serving: the 20 m map from 0 m, the 240 m map from 40 km.

**Sizes:**

```
demo:      400 sites × 4 masts × 1,440 = 2,304,000 values
           float32 (4 B): 9,216,000 B ≈ 9.2 MB each for horizon.npy and blocker.npy
           bool (1 B):    2,304,000 B ≈ 2.3 MB for complete.npy
full grid: 10,000 × 4 × 1,440 = 57,600,000 values × 4 B = 230.4 MB per float array
```

These match `02_CLAUDE.md` §8 ("9 MB", "230 MB").

**Why float32 is enough.** float32 keeps 24 significant bits, so neighbouring values differ by at most 2⁻²³ ≈ 1.19 × 10⁻⁷ of their size.

```
H:  largest real skylines ~23.5° (Shackleton floor)  ->  spacing ≤ 23.5 × 1.19e-7 ≈ 2.8e-6°
    the convergence tolerance is 0.02°, thousands of times larger
D:  up to 250,000 m; values from 131,072 to 262,143 are spaced 2^(17−23) = 2^−6 m ≈ 1.6 cm
```

Inside the engine, geometry stays float64 (`fast.py:26`, `:54`). Only the stored files are float32 (`run_horizon.py:38`).

**What `complete = False` means, and what to do with it.**

- **Code:** "the last sample of the ray has valid terrain" (`fast.py:85–86`; `reference.py:53`).
  - Neither LOLA map in use has no-data pixels (`02_CLAUDE.md` §6).
  - So in practice, False means the ray ran off the map before 250 km.
- **Consequence:** an incomplete H is a **lower bound** on the true skyline.
  - H is a maximum over the samples the ray had.
  - Terrain past the edge can only add samples, and adding samples can only raise a maximum.
  - So Sun and Earth visibility computed from an incomplete ray are *optimistic*. That's why the flag exists, and why `run_horizon.py:87–88` warns with the number of sites affected.
  - Early exit doesn't rescue an incomplete ray. Its bound uses the tallest terrain *on the map* (`fast.py:40`), so it says nothing about terrain past the edge. That's also why `complete` is computed from the last sample, whatever early exit did (`fast.py:85–86`).
  - **My recommendation, not yet agreed with CE 3:** treat a site with incomplete rays as unverified, never as a normal result.
- **When will it happen?**
  - The 240 m map is 3,812 × 3,812 pixels with the pole at index 1,905.5. Along its axes it reaches 1,905.5 × 240 m = 457.3 km from the pole (README Part 2).
  - A ray reaches at most (site's map radius + 250 km), so rays stay on the map for sites within 457.3 − 250 = 207.3 km of the pole.
  - 207.3 km on the map is a colatitude of c = 2·atan(207,320 / (2·1,737,400)) = 2·atan(0.05966) = 0.1192 rad ≈ 6.83°.
  - So Artemis III's 6° zone fits, with 25 km to spare: at 6°, ρ = 2R·tan(3°) = 182.1 km, and 182.1 + 250 = 432.1 km < 457.3 km.

## Try it yourself (Chapter 2)

**1. Make the four files, twice** (README Part 5).

```
python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --out out/demo/sites.csv
python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --fine data/ldem_875s_20m.lbl --out out/demo
python scripts/run_horizon.py data/ldem_75s_240m.lbl out/demo/sites.csv --fine data/ldem_875s_20m.lbl --out out/demo
```

Predict:

- (a) the shape of each array;
- (b) the number of data bytes in `horizon.npy`;
- (c) whether the "rays that left the map" warning prints;
- (d) whether the two runs take the same time.

Answers:

- (a) (400, 4, 1440).
- (b) 9,216,000 bytes, plus a small file header.
- (c) No. The demo sites are within about 5 km of the rim site, which is 6.71 km from the pole: far inside the 207.3 km limit in 2.4.
- (d) The first-ever call compiles the Numba code, and `cache=True` (`fast.py:50`) saves it to disk. So a first run can be slower. If you already did the Chapter 1 runs, the cache may already exist and both runs take about the same.
  - Compare your second run with the 10.3 s measured on 12 threads (`02_CLAUDE.md` §8). The printed time comes from `run_horizon.py:86`.

**2. Read the files the way CE 3 will.** Site 210 is the rim site (`make_demo_sites.py:33`: site n//2·(n+1) = 10·21 = 210 for n = 20).

```python
import json, numpy as np
H  = np.load("out/demo/horizon.npy")
D  = np.load("out/demo/blocker.npy")
ok = np.load("out/demo/complete.npy")
meta = json.load(open("out/demo/horizon_meta.json"))

j = round(90 / (360 / meta["n_az"]))                  # theta = 90 deg
m2, m10 = meta["masts_m"].index(2.0), meta["masts_m"].index(10.0)
print(j, m2, m10)
print(H[210, m2, j],  D[210, m2, j])
print(H[210, m10, j], D[210, m10, j])
print((H[:, m10] < H[:, m2]).all(), ok.all())
```

Predict all four printed lines first. Answers:

- `360 1 3`.
- About 3.3337° and 90.0 m: the near crest.
- About −0.7040° and about 127,510.7 m: the far massif.
- `True True`. A taller mast is lower everywhere (2.1), and every ray is complete.

These match `04_data.json` `ray`, which walked the same site and direction.

**3. Do one Earth lookup by hand, then in Python.** Earth is at θ = 90°, elevation −1.5°. Is it visible from the rim site at 2 m? At 10 m? Use e = el⊕ + r⊕ > H with r⊕ = 0.95°.

```python
for m in (m2, m10):
    print(meta["masts_m"][m], -1.5 + 0.95 > H[210, m, j])
```

Answers:

- 2 m: −0.55 > 3.33 is false, so **hidden**.
- 10 m: −0.55 > −0.70 is true, so **visible**, with only 0.15° to spare.
- That margin is smaller than one of Earth's own discs is wide. Think about what a 0.15° error in H would do to a comms window. Chapter 7 is about making sure we don't have one.
