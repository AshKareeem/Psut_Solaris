# How our horizon engine works

## Part 2: Chapter 3 (geometry from first principles)

Snapshot: commit `7e50c80`; `file:line` refers to that commit.

Every number below comes from the project files or from a calculation shown here. Where a number is new, I computed it by running the project's own code, rebuilt from `03_code.md`. The rebuild passes the test suite exactly as the README says without data: 32 passed, 2 skipped.

The chapter answers three questions, then covers two approximations:

1. **Where is a point?** The map.
2. **Which way is a direction?** θ.
3. **How high does a point look?** The exact formula.
4. One approximation we refuse (the small-angle shortcut), and one we live with for now (straight map rays).

---

# Chapter 3. Geometry from first principles

## 3.1 The map: south polar stereographic

### What the projection does

Imagine a flat sheet touching the Moon at the south pole S. Put a light at the north pole N. Every surface point casts a shadow on the sheet. That shadow position is the point's map position.

```
          N  *                     N = north pole (the light), 2R above the sheet
             |\                    S = south pole, where the sheet touches the Moon
             | \                   P = a surface point, at angle c from S as seen from the Moon's centre
         2R  |  \  angle c/2
             |   \
             |    * P
             |     \
   sheet ____S______*______        P's shadow lands ρ = 2R·tan(c/2) from S
             |<-ρ-->|
```

**Why ρ = 2R·tan(c/2):**

- An angle at the edge of a circle is half the angle at its centre over the same arc (the inscribed-angle theorem).
- At the centre, S and P are c apart. So at N, the line to S and the line to P are c/2 apart.
- The triangle N–S–shadow is right-angled at S, with |NS| = 2R. So ρ = 2R·tan(c/2).

**The code** (`horizon/dem.py:39–48`). Here c = 90° + lat is the angle from the south pole:

```
forward:  ρ = 2R·tan((90° + lat)/2)      x = ρ·sin(lon)      y = ρ·cos(lon)
inverse:  lat = −90° + 2·atan(ρ / 2R)    lon = atan2(x, y)
```

- Note the argument order of `atan2(x, y)` (`dem.py:48`).
  - **Longitude** is measured from +y (map up) toward +x, which is *clockwise*.
  - **θ** is measured from +x, *counterclockwise*.
  - Two opposite conventions, side by side in the codebase. Know which is which.
- Longitude 0 lands at map up (x = 0, y = ρ). Longitude 90°E lands at map right (x = ρ, y = 0).
- PROJ's `+proj=stere +lat_0=-90 … +R=1737400` gives the same x, y to within 1 mm (`tests/test_compare_pgda.py:32`). That's an independent check of these formulas.

### Why this projection works for us

**It preserves angles (it's conformal).** The map stretches distances by the same factor in every direction at a given point. Proof:

```
radial:      map length / surface length = dρ / (R·dc) = sec²(c/2)
sideways:    a circle at angle c is 2π·R·sin c on the Moon and 2π·ρ on the map
             ratio = 2·tan(c/2) / sin c = 2·tan(c/2) / (2·sin(c/2)·cos(c/2)) = sec²(c/2)
```

Both ratios are the same, so small shapes and angles keep their shape. A direction θ on the map is a true direction on the ground, just measured from a fixed map axis.

**It's true scale at the pole, and stretches slowly away from it** (`dem.py:40`). The stretch k − 1, with k = sec²(c/2):

| Angle from the pole c | Map stretch k − 1 |
|---|---|
| 0° (pole) | 0 |
| 0.2214° (rim site) | 0.0004% |
| 1° | 0.0076% |
| 3° | 0.069% |
| 6° (Artemis III limit) | 0.27% |
| 14.18° (end of a 250 km ray from a 6° site) | 1.55% |

That growth is what section 3.6 is about.

### Rows and columns

From `dem.py:29–33`:

```
row = pole_row − y / pixel        col = pole_col + x / pixel
```

- **Row 0 is the top of the image**, so +y means a *smaller* row: hence the minus sign. Every time the code walks north on the map, it subtracts from `row` (`fast.py:68`; `reference.py:39`).
- **An integer (row, col) is a pixel centre.** Bilinear interpolation blends the four centres around a point.
- **The pole sits at index (n − 1)/2** (`dem.py:70`). The 240 m map is 3,812 pixels wide, so the pole is at 1,905.5: on a pixel *corner*, not a centre.
- **A crop keeps the convention.** It shifts the pole's index (`pole_row = center − r0`, `dem.py:93`), so the same x, y still finds the same ground. That's why x, y in metres is the address shared between maps, not (row, col) (team PDF, Step 0).

### Worked example: the rim site

The rim site is pixel (row 1931, col 1894) of the 240 m map (`horizon/sites.py:13`).

```
x   = (1894 − 1905.5) × 240 = −2,760 m
y   = (1905.5 − 1931) × 240 = −6,120 m
ρ   = √(2,760² + 6,120²)     = 6,713.6 m          (6.71 km from the pole)
c   = 2·atan(6,713.6 / 3,474,800) = 0.0038641 rad = 0.2214°
lat = −90° + 0.2214°         = −89.778601°        (RIM_SITE, sites.py:13)
lon = atan2(−2,760, −6,120)  = −155.72556°
```

**On the 20 m map**, the same x, y is −138 and −306 pixels from the pole.

- `04_data.json` says the site sits on a 20 m pixel *corner*. So that map's pole index is also a half-integer.
- Bilinear interpolation at a corner is the plain average of four pixels. That average is the site's ground height, 1,729.25 m.
- It's also why the old terrain patch, sampled at the site plus multiples of 20 m, never hit a real pixel. It showed +8.5 m where the crest pixel is +9.25 m.

## 3.2 Directions: θ, and why compass bearings fail

**A compass bearing is measured clockwise from local north. At the south pole every direction is north.**

- At the pole itself, bearings are undefined.
- Near the pole, "north" swings around:
  - At the rim site, local north points to map direction θ = 245.73°.
  - At the mirror site across the pole (longitude 24.27°), local north points to θ = 65.73°.
  - The two sites are 13.4 km apart, and their norths point in *opposite* directions.
- A bearing-based skyline would need a different rotation at every site. A map-fixed angle needs none.

**θ is fixed to the map: from +x, counterclockwise** (`fast.py:36`; `reference.py:30`). It means the same thing at every site, and cos θ and sin θ give the map step directly (`fast.py:67–68`):

```
col = site_col + cos θ · d / pixel
row = site_row − sin θ · d / pixel        # minus: +y is a smaller row
```

| θ | Map direction | Toward |
|---|---|---|
| 0° | right (+x) | longitude 90°E |
| 90° | up (+y) | longitude 0, **and Earth** |
| 180° | left | longitude 90°W |
| 270° | down | longitude 180° |

**Why Earth sits near θ = 90° for every site, not just at the pole:**

- Earth is so far away that its direction in space is the same from every site.
- Near the pole every site's local horizontal is almost parallel to the map plane: tilted by c, at most 6°. So Earth projects to almost the same map direction everywhere.
- That direction is toward the sub-Earth point near longitude 0 (`02_CLAUDE.md` §2), so θ ≈ 90°.
- The tilt changes Earth's *elevation*, not its direction. That is the c·cos(θ − θ_out) term in `scripts/estimate_visibility.py:9` and `:47`. At the rim site it lowers Earth by 0.2214° × cos(90° − 245.73°) = −0.20°.

**The convention is pinned by a test** (`tests/test_dem.py:67–76`):

- A cone placed 10 km from the pole toward longitude 0 must make H peak at θ = 90°.
- A cone toward 90°E must make H peak at θ = 0°.

**Converting CE 2's SPICE azimuth A (clockwise from local north) to θ:** θ = (β − A) mod 360°, where β is local north's map direction (`02_CLAUDE.md` §5).

- The minus sign is there because A grows clockwise and θ grows counterclockwise.
- At the rim site, β = 245.73°. Local north points straight away from the pole, so β equals `tilt()`'s θ_out (`estimate_visibility.py:31–34`).

Predict before reading on: θ for A = 0°, 90° and 180° at the rim site.

```
A =   0° (north)                ->  θ = 245.73°
A =  90° (east)                 ->  θ = 155.73°
A = 180° (south, to the pole)   ->  θ =  65.73°
check: the pole seen from the site is at atan2(+6,120, +2,760) = 65.73°  ✓
```

Send this worked example to CE 2 with the test name. It catches both classic bugs, a missing minus sign and using map north instead of local north, in one line.

## 3.3 The exact elevation formula, derived

Cut the Moon with the vertical plane that contains the observer and the ray. That plane passes through the Moon's centre O.

```
                                          P   terrain sample, radius R + z
                                        ,*
                                      ,' :
                         sight line ,'   :  up  = (R+z)·cos φ − r_obs
                                  ,' α   :
   observer  Q  o -----------------------+--------->  local horizontal at Q
   radius       |        out = (R+z)·sin φ             (perpendicular to OQ)
   r_obs =      |                     /
   R + h0 + m   |                 /
                |             /   radius R + z
                |   φ     /
                |     /
                | /
                O   Moon's centre             (φ hugely exaggerated: 0.0058 rad at 10 km)
```

**Step by step:**

1. Put O at the origin and the observer straight up: Q = (0, r_obs), with r_obs = R + h0 + m.
   - h0 is the ground height at the site and m is the mast (`fast.py:38`).
2. The sample P is at radius R + z, turned by the central angle φ from OQ: P = ((R+z)·sin φ, (R+z)·cos φ).
3. **φ = d/R**: d is distance along the reference sphere of radius R, and arc = radius × angle (`fast.py:37`; `reference.py:46`).
4. The vector from Q to P is
   - out = (R+z)·sin φ, the horizontal part;
   - up = (R+z)·cos φ − r_obs, the vertical part.
5. The local horizontal at Q is perpendicular to OQ, which is the x direction here. The elevation is the angle of (out, up) above it:

```
α = atan2( (R+z)·cos φ − (R+h0+m),  (R+z)·sin φ )         H(θ) = max α along the ray
```

There is no small-angle step anywhere, so this is exact on a sphere. The only modelling choices are where the samples sit (3.6) and the terrain heights between pixels (Chapter 4).

**Why atan2, and why the code doesn't call it.**

- `atan2(up, out)` is the direction of the vector (out, up), with no quadrant ambiguity.
- But out is always positive here: R + z > 0, and φ is at most 250,016.6 / 1,737,400 = 0.144 rad, far from π.
- For out > 0, atan2(up, out) = atan(up / out) exactly. atan is strictly increasing, so the largest angle belongs to the largest ratio.
- So the engine compares ratios `t = up / out` (`reference.py:48–50`; `fast.py:75–76`) and calls arctan once, at the end (`reference.py:52`; `fast.py:47`). Chapter 5 shows what that saves.
- The test computes its expected value with `np.arctan2` (`tests/test_reference.py:21–22`), a different code path from the engine. That makes it a real check, not the engine checking itself.

**Why measure from the local horizontal.**

- CE 2's SPICE elevations are measured from the plane perpendicular to the Moon's radius at the site (`02_CLAUDE.md` §5). The skyline must use the same plane, or every Step 3 comparison is biased.
- The Sun and Earth are effectively at infinity, so their elevation doesn't change with mast height. Only the skyline does.

### Three worked examples, checked against the engine

**1. The cone test** (`tests/test_reference.py:33–37`): peak 1,000 m at d = 10 km, observer at 0 m.

```
φ   = 10,000 / 1,737,400                = 0.00575573 rad
up  = 1,738,400·cos φ − 1,737,400       = 971.205 m      (not 1,000: the surface curved away 28.8 m)
out = 1,738,400·sin φ                   = 10,005.700 m   (not 10,000: P is 1 km above the sphere)
α   = atan2(971.205, 10,005.700)        = 5.544056°      = the expected value in 02_CLAUDE.md §8
```

**2. The real ray, 2 m mast, best sample** (`04_data.json` `ray`, k = 8): d = 90 m, z = 1,736.5 m, observer 1,729.25 + 2 m.

```
up = 5.248 m    out = 90.090 m    α = 3.33367°     the engine's H at θ = 90°: 3.33367°  ✓
```

**3. The real ray, 10 m mast, best sample** (k = 2120): d = 127,510.7 m, z = 4,859.5 m, observer 1,739.25 m.

```
up = −1,569.844 m    out = 127,752.588 m    α = −0.70402°     engine: −0.70401°  ✓
```

The 0.00001° gap comes from `04_data.json` storing z to 0.1 m.

Look at example 3. The massif is 3,120 m *higher* than the observer, yet it appears *below* level. By 127.5 km the Moon's surface has dropped 4,678 m below the observer's horizontal plane, more than the massif's height advantage. That's curvature, and it's the next section.

## 3.4 The small-angle approximation, and what curvature does

**The approximation.** Use 1 − cos φ ≈ φ²/2 and sin φ ≈ φ, and drop z/R:

```
up  = (z − h) − (R+z)·(1 − cos φ)  ≈  (z − h) − d²/(2R)          h = h0 + m
out = (R+z)·sin φ                  ≈  d
α  ≈  atan( (z − h − d²/2R) / d )          (02_CLAUDE.md §6: "close but not exact")
```

d²/2R is how far the Moon's surface drops below a flat line after distance d.

**How close is "close"?** Computed on the cases above:

| Case | Exact | Approximation | Error |
|---|---|---|---|
| Cone test, 10 km | 5.544056° | 5.547290° | 0.0032° |
| Rim, 2 m mast, crest at 90 m | 3.33367° | 3.33699° | 0.0033° |
| Rim, 10 m mast, massif at 127.5 km | −0.70402° | −0.70043° | 0.0036° |
| Rim, 10 m mast, worst sample on the ray (d = 10 m, a steep −47.7° sight line) | | | 0.028° |

- Most of the error comes from the dropped factor (R + z)/R. At the rim, z ≈ 1.7 km, so it's 0.1%: example 2 had out = 90.090 m, not 90 m.
- On near-level sight lines, which are the ones that decide sunlight, that costs about 0.003°: a sixth of the 0.02° budget, for nothing.
- On steep near-field lines it exceeds the whole budget.
- The exact formula costs no more, because cos φ and sin φ are computed once per step for all rays and sites (`fast.py:46`). So the engine is exact.

**Ignoring curvature altogether (a flat Moon).** The angle becomes atan((z − h)/d). The error is about d/(2R) radians:

| Distance | Surface drop d²/2R | Angle error d/2R |
|---|---|---|
| 1 km | 0.3 m | 0.017° |
| 5 km | 7.2 m | 0.082° |
| 20 km | 115.1 m | **0.33°** |
| 40 km | 460.5 m | 0.66° |
| 100 km | 2,877.9 m | **1.65°** |
| 250 km | 17,986.6 m | 4.12° |

- The Sun never gets higher than +1.54°. Past 93.4 km (where d/2R reaches 1.54°), the curvature error alone is bigger than the Sun's highest elevation.
- On the real ray: with a flat Moon, the 127.5 km massif would sit at **+1.40°** instead of −0.70°, a 2.10° error.
  - The flat-world skyline toward Earth would be at least +1.40°: that's the largest flat-world angle among the ray samples stored in `04_data.json`.
  - The Sun, which never gets above +1.54°, would barely clear it.
  - That's why `02_CLAUDE.md` §6 calls it "a disaster".
- d²/2R itself drifts from the exact drop R(1 − cos φ) at long range: 17,986.6 m vs 17,955.6 m at 250 km. One more reason the engine uses the exact form.

## 3.5 Negative horizons

On a perfectly smooth Moon, an observer at height h sees the horizon *below* level.

```
                 Q  o --------------------------------  local horizontal at Q
                    |`-._
            h       |    `-._      tangent line, dips by angle δ
          __________|________`-*  T   tangent point
                    |         /
                    |       /   R
                    |  δ  /
                    |   /
                    | /
                    O   Moon's centre
```

- The sight line just grazes the sphere at T, so the radius OT is perpendicular to the sight line QT.
- In the right triangle O–T–Q: cos(angle QOT) = R / (R + h).
- The dip below the horizontal equals angle QOT. The horizontal is perpendicular to OQ, and the tangent is perpendicular to OT, so the angle between them equals the angle between OQ and OT.
- So:

```
H = −arccos( R / (R + h) )        distance to T = R·arccos(R/(R+h)) ≈ √(2Rh)
```

| Observer height h | H (smooth Moon) | Distance to the horizon |
|---|---|---|
| 2 m | −0.08694° | 2,636.2 m |
| 5 m | −0.13746° | 4,168.2 m |
| 10 m | −0.19440° | 5,894.7 m |
| 302 m (synthetic rim 300 m + 2 m mast) | −1.06822° | 32.4 km |

- The 2 m row is pinned by `tests/test_reference.py:25–30`: H within 10⁻⁴° of −0.08694° in every direction, and the median D within 50 m of 2,636 m.
- The 302 m row is the "big arc about 32 km away" in README Part 1. You'll reproduce it below.

**The engine never clamps H.**

- `best` starts at −∞ (`fast.py:59`), and missing samples become −∞ in the reference (`reference.py:50`).
- Every real sample contributes its true angle, negative or not.

**Clamping H at 0 would wreck the result.** On the rim site's 1° skylines, with the same model as `estimate_visibility.py` (it reproduces the official 86.6% / 80.4% exactly):

| Case | Directions with H < 0 | Sun (true) | Sun if H were clamped at 0 | Earth (true) | Earth if clamped |
|---|---|---|---|---|---|
| 240 m map, 2 m mast | 96% | 86.6% | 49.4% | 56.3% | 53.6% |
| 20 m + 240 m, 10 m mast | 96% | 80.4% | 49.4% | 56.3% | 53.6% |

A clamp would turn the best spot on Shackleton's rim into an average one. The 10 m mast fix in the pitch would vanish with it.

## 3.6 The straight-map-ray approximation (honestly)

**What the engine does:**

- It walks a straight line on the map: (x0 + d·cos θ, y0 + d·sin θ) (`fast.py:67–68`; `reference.py:38–39`).
- It treats the map distance d as surface distance: φ = d/R (`fast.py:37`).

**What exact geometry would do:**

- Follow the great circle that leaves the site in direction θ.
- Place samples at true surface distance s, and use φ = s/R.

These differ in two ways.

**1. Distance: map distance runs long, always.**

- k = sec²(c/2) ≥ 1 everywhere (3.1). So any path is at least as long on the map as on the Moon.
- The great circle is the shortest surface path.
- So the true surface distance to a sample is ≤ the map distance d. The engine's φ is a little too large.

**2. Direction: straight map lines are great circles only through the pole.**

- A ray from the pole is a meridian, so its direction is exact.
- From any other site, a straight map line slowly leaves the great circle. A sample "at θ" really sits a little off θ.

**Measured on the sphere.** Every direction, samples at map distance 250 km; computed with the project's projection code:

| Site's angle from the pole | Map distance runs long by | Azimuth drift, worst direction |
|---|---|---|
| 0 (pole) | 0.172% (250,000 m vs 249,570 m, 430 m) | 0 |
| 0.2214° (rim site) | 0.159% – 0.187% | 0.008° |
| 1° | 0.117% – 0.243% | 0.036° |
| 3° | 0.053% – 0.429% | 0.108° |
| 6° | 0.070% – **0.823%** | **0.215°** |

- The stretch is worst for rays pointing away from the pole; the drift is worst for rays running sideways.
- This reproduces the "up to 0.8%" and "up to 0.2°" in `02_CLAUDE.md` §9.

**Which way it biases H.**

- A φ that's too large adds too much curvature drop, so distant terrain looks slightly *lower* than it is.
- So the distance error biases H **low**, which means visibility comes out optimistic.
- The direction drift adds scatter of either sign.
- That matches the measured mean of −0.01° for sites 5–6° out (`02_CLAUDE.md` §9).

**How much a distance error costs** (the rim's 127.5 km massif, 10 m mast):

| Distance used is too long by | Massif's angle drops by |
|---|---|
| 0.1% | 0.0035° |
| 0.5% | 0.0175° |
| 0.8% | 0.0279° |

So by 6° from the pole, distance stretch alone can eat the whole 0.02° budget on a distant blocker.

**Measured effect on the skyline** (`02_CLAUDE.md` §9: 240 m map, 10 m mast, final settings; worst site, 99% of its directions; against exact great circles):

| Sites | Error |
|---|---|
| Rim site | 0.003° |
| 0.5–1.5° from the pole | 0.007° |
| 2.5–3.5° | 0.016° |
| 5–6° | **0.048°** (Earth visibility up to 0.15 points) |

**Verdict.**

- Everything validated so far is close to the pole: the rim site, Shackleton's floor, the 100 NASA pixels. So the 0.003° row applies, and those results stand.
- Beyond about 3° the error breaks the 0.02° convergence rule. So the full 6° grid must not run until the fix is in.
- The fix: sample along great circles at true surface distance, then project each sample to the map (`02_CLAUDE.md` §9). The team PDF now says this too ("One approximation", Step 1).

**One honest sentence for a judge:** "We walk straight lines on a polar map. That's 0.003° off at our validated sites but up to 0.05° at 6°, so we switch to great-circle sampling before the full run."

---

## Try it yourself (Chapter 3)

Write each prediction down before you run.

### 1. See curvature and the negative horizon (README Part 1, no download needed)

```
python scripts/plot_horizon.py --synthetic --site shackleton-rim --dmax 60000 --out out/synthetic_rim.png --save out/synthetic_rim.npz
python scripts/plot_horizon.py --synthetic --site shackleton-rim --dmax 60000 --mast 10 --out out/synthetic_rim_m10.png --save out/synthetic_rim_m10.npz
python scripts/plot_horizon.py --synthetic --site shackleton-floor --dmax 60000 --out out/synthetic_floor.png
```

The synthetic rim is 300 m high and the default mast is 2 m (`plot_horizon.py:111`). Predict:

- (a) the lowest skyline, for each mast;
- (b) how far away that lowest skyline is formed;
- (c) the floor's skyline range.

To get D, read it from the saved files:

```python
import numpy as np
for f in ("out/synthetic_rim.npz", "out/synthetic_rim_m10.npz"):
    s = np.load(f); i = np.argmin(s["H"]); print(f, round(float(s["H"][i]), 4), round(float(s["D"][i])))
```

Answers, from running it:

- (a) −1.07° at 2 m, against the formula −arccos(R/(R+302)) = −1.0682°. −1.08° at 10 m, against −1.0823°.
- (b) 32,415 m at 2 m, against √(2R·302) = 32,394 m. 32,806 m at 10 m, against 32,821 m.
  - D lands on the nearest step of the schedule, which is 65 m long at 32 km on this 100 m map.
  - That's the orange arc in the left panel.
- (c) +21.54° to +21.64°, formed 10,450–10,500 m away: the crater's own rim. Never sunlit.

Bonus: the rim skyline's highest point is +2.35° at θ = 79.25°. What makes it? A synthetic 2,500 m cone about 41 km away (`plot_horizon.py:39`).

### 2. Break the direction convention on purpose

In `horizon/dem.py:43`, swap the outputs: `return rho * np.cos(lon), rho * np.sin(lon)`. Predict which tests fail, then run:

```
python -m pytest -q
git checkout horizon/dem.py
```

Answers, from running it (no LOLA data here: 6 failed, 26 passed, 2 skipped):

| Fails | Why |
|---|---|
| `test_dem.py::test_longitude_0_is_map_up_and_90E_is_map_right` | the cone toward longitude 0 now lands at θ = 0° |
| `test_dem.py::test_latlon_round_trip` | the forward and inverse projections no longer agree |
| `test_compare_pgda.py::test_reads_the_right_pixel_with_scaling_and_its_centre` | our x, y no longer match PROJ's |
| `test_estimate_visibility.py::test_tilt_direction_follows_the_map_convention` | θ_out comes out rotated |
| `test_sites.py::test_demo_grid_round_trip` | `read_sites` catches x/y vs lat/lon disagreeing |
| `test_run_horizon.py::test_demo_sites_to_horizon_files` | same check, end to end |

Two lessons:

- **Some tests pass for the wrong reason.** `test_xy_that_disagree_with_latlon_fail_fast` still passes: the deliberately swapped CSV still disagrees with the swapped projection.
- **The two LOLA tests in `test_fast.py` are blind to this bug.** With your data they still pass, so you get 6 failed, 28 passed: both engines receive the same (wrong) site positions. This is my reasoning; I couldn't run them without the maps.
  - A convention bug can't be caught by comparing two engines. It needs a test that pins the convention to the outside world. That's why the longitude test and the PROJ test exist.

### 3. Check the formula by hand on the real ray

Run this from the folder that holds `04_data.json`:

```python
import json, numpy as np
R = 1_737_400.0
data = json.load(open("04_data.json"))
r, g = data["ray"], data["site"]["ground_m_20m_map"]
k, d, z = np.array(r["k"]), np.array(r["d_m"]), np.array(r["z_m"])
for mast, kk in ((2, 8), (10, 2120)):
    i = int(np.flatnonzero(k == kk)[0]); h = g + mast; phi = d[i] / R
    exact  = np.degrees(np.arctan2((R + z[i]) * np.cos(phi) - (R + h), (R + z[i]) * np.sin(phi)))
    approx = np.degrees(np.arctan((z[i] - h - d[i]**2 / (2 * R)) / d[i]))
    flat   = np.degrees(np.arctan((z[i] - h) / d[i]))
    print(mast, round(exact, 5), round(approx, 5), round(flat, 5), round(r[f"H_deg_mast{mast}"], 5))
```

Before running, predict for each mast: which of exact, approx and flat is furthest from the engine's H, and by roughly how much.

Answers:

| Mast | Exact | Approx | Flat | Engine H |
|---|---|---|---|---|
| 2 m | 3.33367 | 3.33699 | 3.33847 | 3.33367 |
| 10 m | −0.70402 | −0.70043 | **1.40178** | −0.70401 |

- At 90 m, curvature is nothing (d²/2R = 0.002 m of drop). All three agree to 0.005°.
- At 127.5 km, the flat Moon is 2.1° wrong and on the wrong side of level. The approximation is 0.0036° off.
