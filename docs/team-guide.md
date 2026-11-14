# LunarWindow: the complete team guide

**Who this is for:** all six members of team Psut_Solaris, whatever your background. When you finish it, you should be able to explain any part of the solution to a judge: what it does, how it works, which NASA data it uses, how we know it is right, and where it stops being right.

**How to read it:**
- Everyone reads Parts 1, 2, 3, 9 and 10 (about 25 minutes).
- Then read the part for your own step in depth (Part 4), and skim the others.
- Every number here comes from the code or the committed results (state of Fri Nov 13, 2026, commit `d4ffbab`).
- If the code and this guide disagree, the code is right. Tell Ash.

| You are | Read in depth | You answer judges about |
|---|---|---|
| Ash (CE, lead) | everything; 4.2 line by line | the horizon engine, the timeline, AI use |
| CE 2 | 4.3, 6 | Sun and Earth positions (SPICE, Horizons, Skyfield) |
| CE 3 | 4.4–4.6 | the safe-landing rules, the landing-error check, the ranking |
| IoT | 4.1, 4.5 (battery) | terrain, slope, sites, the battery |
| BIT | 7, 8 | the web app and what a user sees |
| Business | 1, 2, 5, 6, 9 | NASA data, impact, users, references |

---

## Contents

1. [The challenge](#1-the-challenge)
2. [Our answer in one minute](#2-our-answer-in-one-minute)
3. [The physics you need](#3-the-physics-you-need)
4. [The pipeline, step by step](#4-the-pipeline-step-by-step)
5. [NASA data: what we use and where](#5-nasa-data-what-we-use-and-where)
6. [How we know it is right](#6-how-we-know-it-is-right)
7. [The results](#7-the-results)
8. [The web app](#8-the-web-app)
9. [Risks and limits, with their fixes](#9-risks-and-limits-with-their-fixes)
10. [Judge questions and who answers](#10-judge-questions-and-who-answers)
11. [The repository](#11-the-repository)
12. [Running it](#12-running-it)
13. [Rules we never break](#13-rules-we-never-break)
14. [Glossary](#14-glossary)

---

## 1. The challenge

**NASA Space Apps 2026, "Lunar Landing Site Navigator"** ([challenge page](https://www.spaceappschallenge.org/2026/challenges/lunar-landing-site-navigator/)). The official problem, shortened:

> Missions to the Moon's south pole face extreme lighting and communication constraints. Tools that find Sun and Earth positions at candidate sites exist, but their complicated interfaces make it hard to evaluate critical information efficiently. Create an intuitive tool that lets mission planners, educators and the public compare landing sites and dates quickly, showing Sun and Earth positions relative to the horizon, to assess power generation and direct-to-Earth communication windows.

What it asks for, and where we answer it:

| The challenge asks for | Where we answer it |
|---|---|
| comparing landing **sites** | Best sites, ranked per mast height; the compare view |
| ...and **dates and times** | every landing hour from 2026 to 2030 is checked; each site has its safe landing days |
| **speed** | all the heavy work is precomputed, so the page answers instantly |
| the Sun and Earth **relative to the horizon** | the mission player: the real horizon seen from the lander, with the Sun and Earth tracks |
| **power** potential | the visible fraction of the Sun each hour, and a battery simulation |
| **direct-to-Earth** (DTE) windows | when any part of Earth is above the skyline, to the minute |
| the time left before sunset or Earthset | countdowns in the player |
| solar elevation, shown prominently | the "Solar elevation" chart: the Sun's height against the terrain in its direction |
| notable sites and custom coordinates | named sites (IM-1, IM-2, Shackleton) and "Plan your own mission" (any coordinates) |
| three audiences | plain-English verdicts for the public and educators; exact numbers and files for planners |

**The problem NASA names is usability, not missing science.** Tools like JPL Horizons already give Sun and Earth positions. What they don't give simply is the answer to "If I land here at this hour, do I get power and a link home, and do I survive?"

### Event rules that shape everything

- **Local event:** NASA Space Apps Amman & Aqaba, Fri Nov 13 – Sat Nov 14, 2026.
  - Submission opens Sat 09:00 and closes **Sun Nov 15 at 23:59 local time**.
- **Local judging is live:** a 7-minute pitch plus 3 minutes of Q&A.
  - Local judges choose the Global Nominees.
  - Global judges later see **only the submission form**.
- **One demo link:** a deck of at most 7 slides (the title slide counts) or a video of at most 30 seconds.
- **AI use is allowed but must be declared:**
  - in the "Use of SI" field;
  - and "generated code and data must acknowledge generation in descriptive text and metadata".
  - Our data files already say so: the `provenance` field in every `results.json` and every site file.
- **At least one resource from the challenge's Resources tab must be used.** We use all three: JPL Horizons, NASA Moon Trek and LROC Quickmap (Part 5).
- **Pre-event work:**
  - The rules say teams use the 2-day event to complete projects, and judges may ask about work done before it.
  - We **disclose it openly**. The annotated git tag `pre-event-2026-11-12` marks the state before the event.
  - Everything after the tag is event work: `git log --oneline pre-event-2026-11-12..HEAD` (19 commits on Nov 13; see 11.2).

### The judging rubric (local)

| Criterion | Weight | What it means for us |
|---|---|---|
| Creativity & Originality | 20% | the skyline, battery, landing error and "why" together; landing hours, not just places |
| Validity & Technical Feasibility | 20% | tests, NASA comparisons, stated assumptions. **This is the first tie-breaker** |
| Relevance | 15% | NASA data is the input to every number, not just a citation |
| Impact | 15% | planners, educators and the public; CLPS payload types for each lander preset |
| Sustainability | 15% | static files, laptop-scale compute, zero running cost, MIT licence, tests |
| Presentation & Teamwork | 15% | clear in 7 minutes, a working interface, **each member answers for their own step** |

The rubric also says: "A polished pitch does not replace functional or technical evidence." That is why Part 6 matters so much.

---

## 2. Our answer in one minute

**LunarWindow** takes a spot near the Moon's south pole and a landing hour. It tells you whether a solar-powered lander gets sunlight and a direct link to Earth at touchdown, whether it survives the mission, and why. It also ranks the sites for you.

It works in four steps:

1. **Skyline.** From NASA's LOLA laser-altimeter terrain, we compute the height of the horizon around each candidate site in 1,440 directions, out to 250 km, including the Moon's curvature. This is what the lander "sees".
2. **Sky.** With NASA's SPICE toolkit, we compute where the Sun and Earth are in that site's sky every hour from 2026 to 2030.
3. **Visibility.** Comparing the two tells us, hour by hour, how much of the Sun is above the skyline (power) and whether Earth is (contact).
4. **Decision.** A battery model runs the whole mission from every possible landing hour.
   - A landing hour is **safe** if the lander has power and Earth in view at touchdown, sees Earth for at least half the mission, and never drains its battery below the reserve.
   - Then we check the same hour at 17 points within 100 m, because a lander can miss its target by that much.

**Three things set us apart:**
- **A landing site is a point in time, not just a point on a map.** The same spot is safe on some days and fatal on others. So we rank by **safe landing days**, not by an average.
- **100 m changes the answer.** On the Shackleton rim, a spot 2 m above the ground is almost always dark, while a crest 103 m away is lit about 86% of the time. We check every top site at 17 points within 100 m.
- **Every answer explains itself.** For example: "#1 of 9. Ahead of #2 (site 131): safe landing days if the lander misses by up to 100 m: 46 vs 0." Or: "The Sun ... is 1.65 deg above the skyline (bearing 78 deg, set by the Moon's own curvature)."

**The demo mission** (since Sat Nov 14, 04:00: the only candidate that passes every check, NASA Moon Trek's 5 m terrain included):
- **Where:** site 210, the Shackleton rim site (89.779°S, 155.726°W), with panels and antenna 10 m above the ground.
- **When:** landing on 21 January 2026 at 07:00 UTC.
- **What:** a Nova-C-class lander, for a 14-day mission.
- **At touchdown,** the Sun is 2.98° above the skyline and Earth 0.56°.
- **Over the mission,** the Sun and Earth are in view 100% of the time, there is no darkness, and the battery never dips.
- **Across 2026–2030,** the site has 337 safe landing days. 315 of them stay safe if the lander misses by up to 100 m.
- **Its ground:** 3.9° at the target; the steepest of its 17 points is 6.4°.
- **Rank:** #1 at 10 m. **At 0 and 2 m the same spot has no safe day at all.** That is the whole story of the mast.
- **On NASA Moon Trek's 5 m terrain:** the same verdict (Sun 2.99°, Earth 0.57°; see README Part 9).
- **Failsafe card:** it can land up to 176 h late and stay safe within 100 m, and even a landing one lunar month late is safe. All 17 points are safe, Earth is in view at touchdown, mid-mission and end, and it survives on half the battery (at best, sun-tracking panels).
- **The second example, site 33 at 5 m:** the best 5 m site on our maps (180 safe days, 46 within 100 m). **On Moon Trek's 5 m terrain it fails**: a 7–8 m rise 20 m away hides the Sun and Earth. Use it to show that terrain finer than the map can change the answer (risk P4).
- **At 2 m,** no site survives a 100 m miss (risk R3): at the rim the mast is not optional.

---

## 3. The physics you need

### 3.1 Why the south pole is hard

- **The Sun skims the horizon.**
  - At the pole, the Sun is never more than about 1.5° above or below the level horizon.
  - It goes all the way around the horizon once every 29.5 days or so, so a hill in any direction can block it.
- **Earth stays in one direction.**
  - Earth hangs near the direction of longitude 0, on the near side.
  - Over a month it bobs up and down by about ±6.7° (libration). Depending on the terrain in that direction, that means about two weeks in view and two weeks hidden.
- **Small heights matter.**
  - Both bodies sit so low that a hill 10 km away, standing 1° high, decides whether you have power.
  - A few metres of mast can lift the panels over a nearby crest.
- **Real landers show it:**
  - **IM-1 Odysseus** (Feb 22, 2024) landed near Malapert A and tipped by about 30°. Only one panel was lit, and the antenna pointed badly. It worked for about a week, until the Sun sank low.
  - **IM-2 Athena** (Mar 6, 2025) landed on its side in a crater about 20 m wide near Mons Mouton, in shadow and cold. Its arrays gave only about 100 W, and operations ended less than 13 hours after landing.

### 3.2 The horizon, with curvature

Take an observer at height h₀ + m: the ground height plus the mast. A terrain point at surface distance d (angle φ = d / R) and height z appears at this elevation angle:

```
α = atan2( (R + z)·cos φ − (R + h₀ + m),  (R + z)·sin φ )
```

- **R = 1,737,400 m** is the Moon's reference sphere. LOLA heights are measured from it.
- The horizon in direction θ is the highest α along that ray: **H(θ) = max α**.
- **Curvature can't be ignored.** Leaving it out puts the horizon 0.33° wrong at 20 km and 1.65° wrong at 100 km, while the Sun's whole range is only ±1.5°.
- **The horizon can be negative.** Even a perfectly smooth Moon, seen from 2 m up, has its horizon at −0.087°, below level. So we **never clamp negative horizons to zero**.

### 3.3 The Sun and Earth are discs, not points

The Sun's radius is about 0.27°. Earth's radius, seen from the Moon, is about 0.95° (0.90–1.02° as the distance changes). Both radii are stored for every hour.

- **Sun:** the visible fraction is `s = clamp((sun_el − H(sun_az) + r_sun) / (2·r_sun), 0, 1)`. The Sun "counts as up" when s > 0.5, which means its centre is above the skyline.
- **Earth:** in view if any part of its disc is above the skyline: `earth_el + r_earth > H(earth_az)`.
  - This is NASA's own rule in its PGDA maps.
  - An optional **Earth margin** asks for more; the weak-antenna preset uses 2°.

### 3.4 Why 100 m matters

- NASA's Artemis III reference requirements include landing **within 100 m of the target**.
- On the rim, the terrain changes quickly:
  - The highest rim pixel of the 240 m map is the "rim site". On 20 m terrain, it sits 9.3 m below a crest only 103 m away.
  - At 2 m, the rim site is lit 0.3% of the time and the crest 85.9% (pinned by `tests/test_real_terrain.py`).
- A site that is safe only on its exact point is not safe in practice. That is why the ranking's first metric is safe days **within 100 m**.

### 3.5 Directions: one convention

- **θ is measured from the map's +x axis, counterclockwise, 0–360°.**
  - θ = 90° is map up, toward longitude 0, where Earth is.
  - θ = 0° is map right, toward 90°E.
- **People see compass bearings.** Text shown to people (verdicts, "why" sentences) uses ordinary bearings, clockwise from local north.
- **Converting SPICE.** SPICE gives a compass azimuth A. We convert it with θ = β − A, where β = 90° − longitude is the direction of local north on the map.
- A test pins this: `test_longitude_0_is_map_up_and_90E_is_map_right`.

### 3.6 The map projection

- All the terrain is on a **south polar stereographic** map:
  - ρ = 2R·tan((90° + lat)/2);
  - x = ρ·sin(lon);
  - y = ρ·cos(lon).
- The pole is at the centre of the grid. Row 0 is the top of the image, so +y means a smaller row number.
- PROJ's `+proj=stere +lat_0=-90 +lon_0=0 +R=1737400` matches it exactly (tested).

---

## 4. The pipeline, step by step

```
NASA LOLA terrain (PDS, 240 m + 20 m)          NASA SPICE kernels (NAIF, DE421)
        |                                               |
 Step 0: sites.csv (id, x, y, lat, lon, slope)          |
        |                                               |
 Step 1: skylines  -> horizon.npy, blocker.npy,  Step 2: sky.npz (Sun and Earth az/el,
         complete.npy, horizon_meta.json                 disc radii, every hour 2026-2030)
        \_______________________  _____________________/
                                \/
 Steps 3-4: score_sites.py -> results.json + sites/<id>_<mast>.json
        |        ^
        |        | landing-error check: make_neighbours.py (17 points within 100 m)
        |        |   -> run_horizon.py on those points -> score_sites.py --neighbours
        v
 run_profiles.py (the same for every lander preset) -> build_web.py -> web/data/ -> web/index.html
```

Each step writes files and the next step reads them. Every step can be checked on its own, and the browser never computes physics. One step, one owner:

| Step | What | Code | Owner |
|---|---|---|---|
| 0 | candidate sites, slope | `horizon/dem.py`, `horizon/sites.py`, `scripts/make_demo_sites.py`, `scripts/named_to_sites.py` | IoT |
| 1 | skylines per site and mast | `horizon/fast.py`, `horizon/terrain.py`, `scripts/run_horizon.py` | Ash |
| 2 | Sun and Earth every hour | `scripts/make_sky.py` | CE 2 |
| 3–4 | visibility, battery, safe landings, ranking, landing error | `scripts/score_sites.py`, `scripts/battery.py`, `scripts/events.py`, `scripts/make_neighbours.py` | CE 3, IoT |
| report | one site in full, in plain English | `scripts/site_report.py`, `scripts/analyze.py` | CE 3 |
| web | the app | `web/index.html`, `scripts/build_web.py`, `scripts/serve.py` | BIT |

### 4.1 Step 0: terrain and sites (IoT)

**Terrain maps** (NASA LOLA, from the PDS Geosciences Node):

| Map | Pixel | Covers | Used for |
|---|---|---|---|
| `LDEM_75S_240M` | 240 m | 75–90°S | everything beyond 40 km of a site |
| `LDEM_875S_20M` | 20 m | 87.5–90°S (±75.8 km) | near-field for sites within ~36 km of the pole |
| `LDEM_80S_20M` | 20 m | 80–90°S (±304 km, 1.85 GB) | near-field for sites out to ~6° from the pole |
| Moon Trek `LRO_LOLA_DEM_SPole875_5mp_v04` | 5 m | a window around one site | finest level at the demo site (`analyze --near`) |

- **The reader** is `horizon/dem.py`. It memory-maps the image, so a 1.85 GB file never loads whole, and it reads only the crop the sites need. It **fails fast** if anything is unexpected:
  - not polar stereographic;
  - not centred on −90°/0°;
  - a non-square grid;
  - a wrong data type;
  - a unit other than metres;
  - a reference sphere other than 1,737.4 km.
- `read_polar_geotiff` reads Moon Trek's GeoTIFF with the same checks.
- **The 240 m map is the 12 × 12 block mean of the 20 m map** (1.6 m RMS). So the levels join without offsets.

**Sites** (`sites.csv`: id, x, y, lat, lon, height, slope):
- **Demo grid** (`scripts/make_demo_sites.py`): 20 × 20 = **400 sites, 480 m apart** (a square about 9 km wide), centred on the Shackleton rim site (site 210, 89.779°S, 155.726°W).
  - Everything on the page comes from this grid.
  - **Say "demo grid" when you present it.**
- **Named sites** (`named_sites.csv`, each with a citation):
  - IM-1 and IM-2 at their real landing hours;
  - the Shackleton rim site;
  - the crest 103 m from it;
  - the Shackleton–de Gerlache ridge (NASA's brightest pixel within 30 km of the pole);
  - Apollo 11, kept as an "out of coverage" example.
  
  `scripts/named_to_sites.py` turns them into a `sites.csv`, with the slope over 100 m from the finest map that covers each one. IM-1 reads 12.2°, against NASA's reported ~12°.
- **Gates** (NASA's Artemis III reference): **within 6° of the pole** (latitude ≤ −84°) and **slope under 10° over 100 m**, measured on the 20 m map (`--slope-dem`). 53 of the 400 demo sites pass both.
  - Until Nov 13 the demo slope came from two pixels of the 240 m map, which let five too-steep sites through (risk R2, Part 9).
- **Not done yet:** IoT's full grid of ~2,436 sites out to 6°. It needs a run on `LDEM_80S_20M` (about 5 minutes estimated).

### 4.2 Step 1: the horizon engine (Ash)

**What it computes:** for every site, every mast height (0, 2, 5, 10 m) and each of the 1,440 directions:
- the horizon elevation H(θ);
- the distance to the terrain that sets it (the **blocker** distance);
- whether the ray stayed on the map all the way (**complete**).

**How a ray is walked:**
1. Start at the site, at the ground height of the finest map, plus the mast.
2. Step outward along the **great circle** leaving the site in direction θ, at true surface distance. Project every sample onto each terrain map to read its height (bilinear interpolation).
3. Use the right map for each stretch: **20 m terrain within 40 km, then the 240 m map out to 250 km** (with Moon Trek's 5 m map within 4 km when `--near` is given).
4. Keep the highest elevation seen. That is H(θ), and its distance is the blocker distance.

**Why it's fast** (`horizon/fast.py`, about 3.5 ms per site on 12 threads):
- **Precomputed tables:** d, cos φ, sin φ, cos θ and sin θ are computed once, outside the loops.
- **Compare tangents, not angles:** one `atan` per ray, at the very end.
- **Exact early exit:**
  - A bound on the tangent of anything farther out shrinks with distance. It uses A = R + the tallest terrain.
  - Once the best tangent so far beats the bound, nothing farther can win, so the ray stops.
  - It is exact, not an approximation.
- **Step schedule:** step = max(pixel/2, κ·d) with κ = 0.002, so the steps grow with distance. That is 2,458 steps to 250 km on a 20 m grid.
- **Parallel:** Numba compiles the loop and runs sites on every CPU core (`prange`). Terrain is float32; geometry is float64.
- **The demo grid,** 400 sites × 4 masts, runs in about 10 seconds.

**Two engines, same answers:**
- `horizon/reference.py` is a plain NumPy version for one site: the ground truth.
- `horizon/fast.py` must match it to within 1e-6°, with blocker distances bit-identical. Tests check this on synthetic terrain, map edges, no-data holes and real LOLA terrain.

**Settings and their evidence** (`scripts/convergence.py`; they live only in `horizon/__init__.py`):

| Setting | Value | Why |
|---|---|---|
| directions | 1,440 (0.25°) | the worst site is within 0.010° (240 m) and 0.018° (20 m near-field) in 99% of its directions; 720 fails |
| range | 250 km | 200 km misses distant massifs (0.68° off); 250 and 300 km agree to 0.0000° |
| step factor κ | 0.002 | a finer κ changes nothing at 1,440 directions |
| 20 m radius | 40 km | 20 km leaves sectors 0.044° off; 40 km is within 0.009° of 60 km |
| masts | 0, 2, 5, 10 m | the heights a lander could carry its panels and antenna at |

- **The rule:** choose the cheapest settings where every site's skyline is within 0.02° of the finest reference in 99% of its directions.
- **Great circles (fixed Nov 11):** walking straight map lines drifted up to 0.048° for sites 5–6° from the pole. Rays now follow great circles, which match an independent spherical-trigonometry walk to 1e-6°.
- **No max-pyramid:** we measured it, and a pooled-and-interpolated pyramid still misses peaks. Direct 20 m sampling is simpler and more accurate.

**Outputs** (`scripts/run_horizon.py`):
- `horizon.npy`, `blocker.npy` and `complete.npy`, each shaped [sites, masts, 1440].
- `horizon_meta.json`, which holds the settings. **Always read `n_az` and `masts_m` from it; never assume them.**
- Direction j is θ = j · 360 / 1440.

**Edge cases:**
- A ray that leaves the map is flagged `complete = False`, never hidden.
- Sites with any incomplete ray at a mast are not ranked at that mast.

### 4.3 Step 2: the sky (CE 2)

`scripts/make_sky.py` uses NASA's **SPICE** toolkit (through SpiceyPy) to find the Sun and Earth in each site's sky, every hour.

- **Kernels** (from NAIF, downloaded into `data/kernels/`):
  - `naif0012.tls` (leap seconds);
  - `de421.bsp` (planet and Moon positions);
  - `moon_pa_de421_1900-2050.bpc` (the Moon's orientation);
  - `moon_080317.tf` (the Moon's frames).
- **Frame:** `MOON_ME_DE421`, the Mean Earth / polar axis frame that LOLA's maps use.
- **Elevation** is measured from the plane perpendicular to the Moon's radius at the site, the same "level" the skylines use. **Azimuth** is converted to θ (3.5).
- **Disc radii** come from the Sun's radius (695,700 km), Earth's mean radius (6,371 km) and each hour's distance.
- **Span:** 2026-01-01 to 2030-12-31, hourly (1,826 days, about 12 seconds to compute for the demo grid).
- **Output** `sky.npz`: `sun_az`, `sun_el`, `earth_az` and `earth_el` [sites, hours], `sun_radius_deg` and `earth_radius_deg` [hours], and the site ids and coordinates, so the order can be checked.
- **Checked twice, independently** (Part 6):
  - against **Skyfield**, worst 0.00032°;
  - against **NASA JPL Horizons**, 124 positions all within 0.0003°.

### 4.4 Step 3: visibility (CE 3)

For every site, mast and hour (`scripts/events.py` holds the only implementation; everything else calls it):

```
s = clamp((sun_el − H(sun_az) + r_sun) / (2·r_sun), 0, 1)     visible fraction of the Sun
e = earth_el + r_earth > H(earth_az) + earth_margin           Earth in view (any part of the disc)
b = (s > 0.5) and e                                           power and Earth contact together
```

- H is interpolated between neighbouring directions.
- **Sun clearance** = `sun_el − H(sun_az)`: how high the Sun's centre stands above the skyline. This is the "solar elevation" the challenge wants shown prominently.
- **Earth clearance** = `earth_el + r_earth − H(earth_az) − margin`.
- **Shares over a mission:** `f_sun` (share of hours with s > 0.5), `f_earth` (with e) and `f_both` (with b).

### 4.5 Step 4: safe landings, battery, ranking (CE 3 + IoT)

`scripts/score_sites.py`. **There is no weighted score anywhere.** Every number is a physical quantity or a count.

#### The battery model (IoT, `scripts/battery.py`)

```
E(t+1) = min(e_max, E(t) + (p_panel · s(t) − p_load) · 1 h),  never below 0;  the lander starts full
```

| Number | Value | Source |
|---|---|---|
| panel power, p_panel | 200 W | Nova-C maximum solar power (Wikipedia) |
| battery, e_max | 700 Wh | 25 Ah × 28 V (IoT, calculated) |
| load, p_load | 50 W | **estimate**, from Odysseus lasting 10–20 hours on battery (Reuters) |
| reserve, e_min | 140 Wh | **assumption**: 20% of a full battery |

- **Bridge:** a full battery lasts (700 − 140) / 50 = **11.2 hours with no Sun**.
- **The model is a sun-tracking array:** power = panel power × visible Sun fraction, whatever the Sun's direction.
  - Real polar landers have fixed panels, so **survival here is an upper bound**.
  - The product says so in every verdict.
- `step()` is the only copy of the formula. Every simulation calls it.

#### Safe landing hour, safe day

A mission of `--days` (14 by default) can start at **any hour** of the sky file: 43,489 possible landing hours in 2026–2030. A landing hour is **safe** when all three hold:
1. **Touchdown:** in the landing hour, more than half the Sun is visible **and** Earth is in view (power and a link at landing).
2. **Earth for the mission:** Earth is in view for at least **50%** of the mission hours (NASA: direct-with-Earth, no relay).
3. **Survives:** the battery never drops below e_min.

- A **landing day** (UTC) is safe if any of its hours is safe. **`safe_landing_days`** counts them. It is the headline number: how many chances you get to launch.
- **Battery needed** = e_max − the lowest level reached, taken at the worst safe landing hour. Partial Sun keeps charging during a dim spell, so this comes from the simulation, not from darkness × load.

#### The landing-error check (within 100 m)

1. `scripts/make_neighbours.py` puts **17 points** around every ranked site: the site, plus 8 directions at 50 m and at 100 m. One set covers every lander preset.
2. `scripts/run_horizon.py` computes their skylines. Each point uses its parent site's sky, because 100 m moves the Sun and Earth by only about 0.003°.
3. `score_sites.py --neighbours` counts a date as safe for the site **only if it is safe at all 17 points**. That gives `safe_days_within_100m`.

#### Ranking: one list per mast height

- **Gates first:**
  - within 6° of the pole;
  - slope under 10°;
  - every ray complete at that mast;
  - at least one safe landing date.
- **Then, in order** (`meta.ranking_keys` in `results.json`):
  1. **most safe landing days if the lander misses by up to 100 m;**
  2. **most safe landing days on the exact point;**
  3. **least battery needed** at the worst safe landing.
- **Rank sentences:**
  - Every ranked site gets `rank` and a plain sentence, `rank_reason`. It names the metric that puts the site ahead of the next one and behind the one before, with both numbers.
  - It is computed once, in Python (`rank_reasons()` in `score_sites.py`). The page only shows it.
- **Why no weighted score:** weights are opinions dressed as numbers. A judge can ask "why 0.3 and not 0.4?", and there is no physical answer. Our three metrics are counts and watt-hours that anyone can check.

#### Per site and mast

- **Recommended mast:** the shortest mast with a safe date on the point (`recommended_mast_m`) and within 100 m (`recommended_mast_100m_m`).
- **Best dates:** up to 3 safe days. They are ordered by most hours of power and Earth together, then shortest darkness, then earliest.
- **Headline landing** (`headline_start`): the one landing every number on the page describes, along with the site's mission file `sites/<id>_<mast>.json`. It is the best date safe within 100 m when that check found one, else the best on the exact point.
- **`longest_dark_h`:** the longest run of hours without the Sun. This is the cold soak, so it also stands for the thermal risk.

#### Lander presets: "Your lander" (`scripts/profiles.py`, `scripts/run_profiles.py`)

Each preset is a set of **mission requirements, never weights**. Each one is a complete Step 4 run, so the page only loads a different `results.json`.

| Preset | Changes | Stands for (CLPS payload examples) |
|---|---|---|
| **Nova-C-class, 14 days** (default) | nothing | landing sensors (NDL lidar, SCALPSS cameras), beacons (LN-1), power-hungry science (PRIME-1 drill), as flown on IM-1 and IM-2 |
| **Long mission: 28 days** | `--days 28` | long-duration science that must outlast a lunar night: heat-flow probes, seismometers (Blue Ghost carried LISTER) |
| **Weak antenna** | `--earth-margin 2` | communication-heavy payloads with a low or blocked antenna: a radio beacon, a surface network (IM-2 carried a Nokia 4G/LTE network) |

#### Sensitivity (`scripts/sensitivity.py`, re-run Nov 14 on the current demo data)

How much the answers depend on the two weakest inputs (demo grid, 14 days, any landing hour; the 140 Wh reserve stays fixed):

| Battery | Hours it bridges with no Sun | Sites with a safe date at 0 / 2 / 5 / 10 m |
|---|---|---|
| 700 Wh (our Nova-C-class lander) | 11.2 h | 31 / 43 / 54 / 61 |
| 1,400 Wh | 22.4 h | 52 / 64 / 73 / 79 |
| 2,800 Wh | 44.8 h | 98 / 116 / 130 / 136 |

- **Antenna mask:** needing Earth 2° above the skyline cuts Earth-in-view time at the median site and mast from 42% to 32%.
- **The answer for judges:** "Double the battery and 50% more sites have a safe date at 2 m; the ranking method doesn't change, only the lander's numbers. That's why the lander is an input."

### 4.6 One site in full: events, verdict, why (CE 3)

`scripts/site_report.py` builds the mission file `sites/<id>_<mast>.json`. It is the same file for a ranked site and for any coordinates.

- **Events** (`scripts/events.py`):
  - the sunlit, DTE and "both" windows;
  - each start and end found as the linear zero crossing of the clearance between two hourly samples, **to the minute**;
  - `hours_to_sunset` and `hours_to_earthset` from the landing time.
- **Verdict:** plain-English sentences: touchdown margins, shares of the mission, survival, darkness, battery used, and the battery-model caveat.
- **Why:**
  - **For a marginal touchdown** (the Sun's centre or Earth's top under 0.5° above the skyline at landing): the terrain that sets it.
  - **For a body that never sets:** its closest pass.
  - **Otherwise:** what blocks the Sun in the darkest spell and Earth in the longest blackout, with distance and compass bearing.
  - **If rays left the map,** it says so.
- **Provenance:** every file states it was computed from NASA LOLA and SPICE, with AI-assisted code verified by tests and the PGDA comparison.

### 4.7 Any site, any hour (`scripts/analyze.py`, `scripts/serve.py`)

- **`analyze(lat, lon, mast, start, days, coarse, fine)`** runs the real pipeline for one point:
  - it computes the skyline on LOLA;
  - it computes the sky with SPICE, for any hour from 1900 to 2049;
  - it runs the battery model.
- It writes the same report in 1–3 seconds and states the terrain maps it used. **Beyond ~81.9°S there is no 20 m map, and it runs on 240 m only.** That map smooths away crests near the site (the rim site looks lit at 240 m and is dark at 20 m), so say so.
- **`scripts/serve.py`** serves `web/` and answers `POST /api/mission`. That powers **"Plan your own mission"** on the page.
  - It needs the maps, the kernels and a laptop, so it doesn't run on a static host.
  - A bad request gets a clear error, never a guess.

### 4.8 Building the web data

- **`scripts/build_web.py --profiles out/profiles_r3`** --region out/region/region_summary.json copies each preset's `results.json` and the mission files it names into `web/data/`. It also writes `profiles.json` and `named_sites.json`, and builds the Moon textures in `web/assets/`.
  - It checks the version and the preset of every file.
  - **Never hand-edit `web/data/`.**
- **`scripts/build_standalone.py`** packs the whole page into one file (`web_standalone/lunarwindow_standalone.html`, about 13 MB) that opens by double-click, with no server. Hand-set missions still need `serve.py`.
- **The schema** is in `docs/ui-data-contract.md`.

---

## 5. NASA data: what we use and where

| NASA resource | On the Resources tab? | What we use it for | Where |
|---|---|---|---|
| **JPL Horizons** | yes | independent check of every Sun and Earth position: 124 positions within 0.0003° | `scripts/validate_horizons.py` |
| **NASA Moon Trek** | yes | 5 m LOLA terrain at the demo site (finest level); LROC NAC photo mosaic around it | `scripts/moontrek.py`, `analyze --near` |
| **LROC Quickmap** | yes | "View in NASA Quickmap" on every site, centred on it, south polar projection | `quickmapUrl()` in `web/index.html` |
| LOLA polar DEMs (PDS) | no | the terrain behind every skyline: 240 m and 20 m | `horizon/dem.py` |
| NAIF SPICE (DE421) | no | Sun and Earth every hour | `scripts/make_sky.py` |
| PGDA illumination maps | no | validation, pixel by pixel; the planner map's base layers | `scripts/validate_pgda.py`, `web/assets/pgda_*.jpg` |
| NASA SVS CGI Moon Kit | no | the 3D globe's colour map and relief | `scripts/build_web.py` |
| Artemis overview for Space Apps (NTRS) | no | the requirements: within 6°, slope < 10°, DTE without relay, land within 100 m | the gates and the 100 m check |

**For the "NASA Data" field,** list the Resources-tab tools first (Horizons, Moon Trek, Quickmap), each with one line on how it is used, then the rest. The full references are in the README.

---

## 6. How we know it is right

| Check | Against | Result | Honest note |
|---|---|---|---|
| Synthetic terrain | exact answers | smooth Moon −0.08694° (exact); cone 5.544056° (exact); ring crater within 0.017° | the ring error is bilinear interpolation shaving the crest |
| Fast vs reference engine | our NumPy reference | within 1e-6°, blocker bit-identical | |
| Great circles | an independent spherical-trig walk | within 1e-6° | |
| Convergence | the finest settings | every site within 0.02° in 99% of directions | it chose the settings (4.2) |
| Shackleton floor | known permanent shadow | skyline 19.75–23.52° all round: never sunlit | |
| **NASA PGDA sunlight and Earth maps** | NASA's 60 m maps, 18.6 years hourly | rim site, 2 m: **Sun r = 0.92, bias +0.1 points, 94% of pixels within 10 points**; Earth 0.85 / +0.6 / 89%. Ridge: Sun 0.83 / +1.9, Earth 0.90 / +2.2 | **2 m is the best-fit height**, so this checks the method; PGDA uses the same LOLA terrain |
| **JPL Horizons** (Resources tab) | NASA's ephemeris service | **124 positions, all within 0.0003°**; elevation within 0.00004° | |
| Skyfield | an independent library | worst 0.00032° | |
| **Moon Trek 5 m** (Resources tab) | our 20 m map | the same verdict for the demo mission; heights agree to a median 1.2–2.2 m on landing slopes | a **210 m spike** 582 m from site 190 would have faked a 4-hour shadow; found and removed (0.12% of pixels, recorded) |
| IM-1 replay | a real landing | terrain sunset 2 Mar 2024, 14:17 UTC; Odysseus died 29 Feb with the Sun ~5° up | 240 m only; supports "attitude, not terrain" as a **hypothesis** |
| IM-2 replay | a real landing | its target was lit at touchdown (Sun 1.60° above the skyline) | **the tool did not predict IM-2's death**: it tipped into a ~20 m crater, about one pixel of the finest map |
| Automated tests | | **151 pass** (`python -m pytest tests -q`) | real-data tests skip when `data/` is missing |

Two independent sources (Horizons and Skyfield) agree with our sky to well under 1/500 of the Sun's radius. **That leaves terrain as the only real source of error.** The convergence study, the PGDA maps and Moon Trek's 5 m terrain check it.

**The pitch line:** "At 100 of NASA's 60 m pixels around Shackleton's rim, our engine matches NASA's sunlight map: correlation 0.92, average difference under half a point."

---

## 7. The results

All from the 400-site demo grid, Nova-C-class lander, 14 days, unless stated otherwise.

**Ranked lists** (sites that pass every gate and have a safe date): 7, 8, 9 and 10 sites at 0, 2, 5 and 10 m.

| Site | Mast | Rank | Safe days (exact point) | Safe days within 100 m | Note |
|---|---|---|---|---|---|
| **33** | **5 m** | **#1 of 9** | **180** | **46** | the demo site; all 17 points under 10° (steepest 9.2°) |
| 131 | 5 m | #2 of 9 | 229 | 0 | more days on the point; 6 of its 17 points are too steep |
| 72 | 2 m | #1 of 8 | 219 | 0 | the 2 m list: no site survives a 100 m miss, so it ranks by days on the point |
| 190 | 2 m | #5 of 8 | 79 | 0 | the old demo site: 2 of its 17 points are 10° or steeper (up to 11.7°) |
| 210 (the rim site) | 10 m | #1 of 10 | 337 | 315 | dark at 0 and 2 m; all 17 points gentle |
| 33 | 10 m | #2 of 10 | 215 | 139 | |

**The story the numbers tell:**
- **Site 33 vs site 131 at 5 m:** 131 has more safe days on its exact point (229 vs 180), but 6 of its 17 landing points are too steep, so a 100 m miss can put the lander on unsafe ground. Site 33 keeps 46 days. That is why 100 m is the first ranking key.
- **At 2 m nothing survives a 100 m miss:** either a point is too steep, or the Sun or Earth is blocked at one of them. The finding: at the rim, a mast of about 5 m is a requirement, not an option.
- **Site 210:** the highest rim pixel of the 240 m map. It is useless at 2 m and the best site at 10 m. The mast is a design decision, so the page ranks each height separately.

**The demo mission** (site 210, 10 m, 2026-01-21 07:00 UTC, 14 days), from `web/data/sites/210_10.0.json`:
- **At touchdown:** the Sun is 2.98° and Earth 0.56° above the skyline.
- **Over 14 days:** the Sun and Earth are in view 100% of the time. There is no darkness, no Earth blackout, and the battery stays full.
- **Closest the Sun comes to setting:** 1.05° above the skyline on 2026-02-01 23 UTC (bearing 160°, set by the Moon's own curvature).
- **Closest Earth comes to setting:** 0.53° above the skyline on 2026-02-04 06 UTC (bearing 161°).
- **Neither sets** during the mission.
- **NASA Moon Trek's 5 m terrain gives the same verdict** (`out/analyze/site210_10m_5m.json`).

**Site 33 at 5 m on Moon Trek (Nov 14):** it passes on our 20 m map but fails on the 5 m map, at 5 m and at 10 m.
- **What the 5 m map shows:** a 7–8 m rise only 20–25 m away (bearings 104° and 137°) hides the Sun and Earth at touchdown. The 20 m map shows about 1 m there.
- **How far apart the two maps are:** within 2 km, the 5 m map (averaged to 20 m) differs from the 20 m map by a median of 4.2 m (95th percentile 28 m). At site 190 the gap was 1.2–2.2 m.
- **What we can't tell:** whether the rise is real or an artifact of the older 5 m product.
- **The honest line:** "finer terrain can change the answer, which is why we check it, and why the demo is a site that passes on both."

**Lander presets:**
- **28 days:** no site at 0, 2 or 5 m has a safe date. At 10 m only site 210 does (427 days; 420 within 100 m).
  - Over 28 days the Sun sweeps the whole horizon and passes behind every ridge.
  - The 11.2-hour bridge can't cover the longer darkness.
  - **The finding:** long missions need a bigger battery or a taller mast.
- **Weak antenna (Earth 2° up):** the same order with fewer days. Site 33 at 5 m drops from 180 to 135 safe days (35 within 100 m).

**Rim vs crest (Part 3.4):** at 2 m, 0.3% Sun on the rim site vs 85.9% on the crest 103 m away.

**The whole region (Nov 14, `docs/region-results.md`):** all 2,436 candidate sites within 6° of the pole (IoT's grid, 5 km apart) went through the same pipeline, tile by tile (`scripts/run_region.py`).
- 2,385 pass the gates, and no ray left the map.
- Sites with a safe landing day at 0 / 2 / 5 / 10 m: **74 / 116 / 147 / 168**. Still safe after a 100 m miss: at least **3 / 49 / 74 / 98**.
- **Best: site 422** (87.047°S, 24.187°W): 77 safe days within 100 m at 2 m, 149 at 5 m, 162 at 10 m.
- **NASA PGDA at site 422:** Earth 55.8% (ours, 2 m) vs 54–55% (NASA); Sun 48% vs 46.6% on its own pixel.
- **So the 2 m finding is local:** at the Shackleton rim no 2 m site survives a 100 m miss, but elsewhere many do.

---

## 8. The web app

`web/index.html`, BIT's design, is one page. It reads only `web/data/`.

| Section | What the user does and sees |
|---|---|
| **Hero** | a 3D Moon (NASA SVS colour map lit with LOLA slopes) with the named landers |
| **Mission planner: Your lander** | picks a lander preset; sees its description and the CLPS payload types it stands for |
| **Candidate sites** | a map of the demo grid over NASA's PGDA sunlight and Earth-visibility maps; one height control (0/2/5/10 m) drives the map, ranking, compare and player |
| **Site** | the selected site's numbers, verdict tiles, **"Why #N at X m"** (or why it isn't ranked), and **"View in NASA Quickmap"** |
| **Best sites** | the ranked list for this height, all three metrics in every row, and **"How we rank"** (gates and the three metrics, no weights) |
| **Compare sites** | sites side by side for the same height, using each one's headline landing |
| **Play the mission** | the horizon seen from the lander, the Sun and Earth moving hour by hour, countdowns to sunset and Earthset, and a timeline of sunlight, Earth contact and battery on one shared playhead |
| **Solar elevation** | the Sun's height against the terrain in its direction: the power margin |
| **Failsafe card** (built Nov 14; open `index.html#site=210&mast=10`) | what if the landing slips 1 h, 6 h, 24 h or a lunar month; which of the 17 points within 100 m fail and why; Earth-contact plan (touchdown, mid-mission, end); each dark spell against the battery; half the battery; how many minutes a 0.02° skyline error moves sunset and Earthset; what the tool cannot see. Fields: `risk`, `contact_plan`, `dark_verdict`, `weak_battery`, `words`, `confidence` in `docs/ui-data-contract.md` (`risk` only for ranked sites) |
| **Plan your own mission** | any coordinates, hour, length, mast, battery, panel, load and Earth margin; runs the real engine through `serve.py` (local server only) |
| **How it works** | Skyline → Sun and Earth → Power and contact → Decision |
| **Why it's hard** | the Sun, a day, shadows, Earth in the sky: the Moon vs Earth |
| **Why trust it** | the NASA PGDA match, Horizons, Moon Trek, terrain-sky alignment, the tests |

**Rules for the page:**
- **It computes no physics.** Every number comes from the Python pipeline's files.
- **It shows no sample data.** A missing file shows an error naming the file.
- **It uses no NASA logos.**
- **New fields come from the pipeline.** If the page needs a new field, ask Ash or CE 3 to add it there, then rebuild with `build_web.py`.

**Hosting:**
- **Static host (e.g. GitHub Pages from `web/`):** everything works except "Plan your own mission", and the card says that it needs the local server.
- **Offline:** the standalone file.
- **Live judge demo:** `python scripts/serve.py` on the laptop.

---

## 9. Risks and limits, with their fixes

Say these before a judge finds them. Saying them out loud is part of Validity. **Status:**
- **FIXED:** changed in the code and the data.
- **SAY IT:** a real limit; disclose it and give the answer line.
- **DECIDE:** a choice for Ash, with the evidence.

Risk review of Fri Nov 13, evening. The numbers are from the rebuilt data (`out/profiles_r3`, with option A).

### 9.1 Ranking risks

| # | Risk | Status | Fix, or what to say |
|---|---|---|---|
| R1 | **Most headline landings were marginal.** 36 of 39 mission files touched down with the Sun or Earth under 0.5° above the skyline. Most top sites have 100% power and Earth together, so dates tied, and ties went to the earliest hour, when Earth is just rising (site 210 at 10 m cleared by 0.05°). A few metres of terrain error would flip them. | **FIXED** | The best date now prefers a **firm touchdown**: the Sun's centre and Earth's top both at least 0.5° clear (the report's own marginal threshold, `firm_touchdown()` in `score_sites.py`). Then come the most hours together, the shortest darkness, and the earliest. Rankings are unchanged (they count days); only the date shown changes. After the fix: 0 of 34 mission files are marginal (was 36 of 39); the demo landing (site 190, 2 m, 2028-09-02 00 UTC) is unchanged. Test: `test_a_firm_touchdown_beats_a_marginal_one_with_more_hours`. |
| R2 | **The slope gate used a placeholder slope.** The demo grid's slope came from two pixels of the 240 m map, a 480 m baseline, not NASA's 100 m. Five ranked sites passed at 5.5–9.7° but are 10.8–13.9° over 100 m on the 20 m map: 52, 230, 330, 380, 381. The page labelled them "over 100 m", which was not true. | **FIXED** | `make_demo_sites.py` now requires `--slope-dem` and computes the slope over 100 m on the finest map with `height_and_slope()`, the same function the named sites use. The placeholder `slope_deg()` is deleted. Site positions are identical, so the skylines are unchanged. Sites under 10°: 56 → 53. The gate now drops 52, 230, 330, 380 and 381, and admits 170 (9.98°) and 209 (9.23°), which the placeholder had wrongly rejected (10.4° and 12.6°). **Site 170 is now #1 at 2 m (37 days within 100 m vs 190's 18)**, so the 2 m pitch line changed (see R3). |
| R3 | **The 100 m check did not check slope.** The 17 points inherit the parent's slope. On the 20 m map, only sites 33 and 210 keep all 17 points under 10°. **The new #1 at 2 m, site 170, is 9.98° at its centre (0.02° under the gate) and has 12 of 17 points at or above 10° (worst 13.8°); site 209 (#3) has 12.** The demo site 190 has 2 (worst 11.7°); site 72 has 1. | **FIXED (option A)** | Option A (strict, NASA's 100 m reading): a date is safe within 100 m only if all 17 points are also under 10°. Then no site at 2 m is safe within 100 m, and at 5 m only site 33 is (46 days). Option B (as now): the gate is the slope over 100 m at the target, and the 17 points check light and Earth. Say B plainly: "the 100 m check is for lighting and Earth; slope is gated at the target". Either way, show the worst slope within 100 m on the page. **Decided Nov 13 night: option A, built.** Each of the 17 points carries its own slope over 100 m on the 20 m map (`make_neighbours.py --slope-dem`); one point at 10° or more makes every date unsafe within 100 m. `results.json` adds `slope_max_within_100m_deg` and `steep_points_within_100m` per site. Result: no 2 m site survives a 100 m miss; site 33 is #1 at 5 m and the new demo. |
| R4 | **The third ranking metric barely decides anything.** Battery needed is taken at the worst safe landing, which by definition barely survives, so nearly every ranked site needs 540–560 Wh of the 560 Wh usable. Measured: it decides **0 of the 68** rank sentences across the three presets. | **SAY IT** | "It's a tie-breaker; at their worst safe landing almost every site needs nearly the whole battery." A more telling metric (battery used at the headline landing) would change the ranking's meaning, so it is Ash's call and not for the night before judging. |
| R5 | **Leads can be narrow.** At 5 m, site 33's #1 rests on 46 days within 100 m against 0, out of 1,813, and it fails on Moon Trek's 5 m terrain. The demo site 210 at 10 m leads by 315 to 139 and passes on Moon Trek. We never tested how terrain height error (metres, Barker et al. 2021) moves it. | **SAY IT** | "The geometry is validated; terrain error is the main uncertainty, which is why we check 100 m and re-checked the demo on Moon Trek's 5 m terrain." Future work: perturb the terrain by its stated error and re-rank. |
| R6 | **17 points, not the whole circle.** A bad pocket between them would be missed. | **SAY IT** | 8 directions at 50 m and 100 m; denser rings are a parameter of `make_neighbours.py` if time allows. |
| R7 | **The slope depends on the map.** Site 190: 8.2° on the 20 m map, 6.8° on Moon Trek's 5 m map. A site near 10° can flip between maps. | **SAY IT** | The gate uses the finest map that covers the whole grid (20 m). The 5 m map covers only a window at the demo site. |
| R8 | **"Best" meant best in the demo grid**: 400 sites about 9 km across. | **FIXED (Nov 14)** | All 2,436 sites within 6° were run (`docs/region-results.md`). The page still shows the demo grid; the region is on slide 6. Sites more than 5° out are beyond the convergence study. |
| R9 | **At 0 m no site is safe within 100 m**, so the 0 m list ranks by days on the exact point. | **SAY IT** | The page states each rank's deciding metric (`rank_reason`), so this is visible, not hidden. |

### 9.2 Physics risks

| # | Risk | Status | Fix, or what to say |
|---|---|---|---|
| P1 | **The battery assumes sun-tracking panels.** Our own IM-1 replay blames Odysseus's death on fixed, tipped panels while the Sun was still ~5° up. The load (50 W) is an estimate, the reserve (20%) an assumption, and there is no heater load in the dark. | **SAY IT** | "Our survival verdict is an upper bound for sun-tracking panels. The product and our IM-1 write-up both say so. Fixed-panel geometry is next." `sensitivity.py` shows how answers move with battery size (re-run it before quoting). |
| P2 | **"Earth for half the mission" is our threshold.** NASA asks for direct-with-Earth contact with no relay, not a share. | **SAY IT** | "It's a mission requirement we chose and state (`min_dte_share` 0.5, in `results.json`)." It is a parameter (`--min-dte-share`) like the presets. |
| P3 | **"Earth in view" is not a working link.** Any part of the disc counts (NASA's visibility rule). No antenna gain, pointing or data rate. | **SAY IT** | The weak-antenna preset needs 2° of clearance. A link budget is future work. |
| P4 | **Terrain finer than 20 m is invisible.** IM-2's ~20 m crater is about one pixel. Beyond ~81.9°S only the 240 m map exists, and it can turn a dark spot lit (rim site: lit at 240 m, dark at 20 m). **Seen again on Nov 14:** site 33 passes on 20 m and fails on Moon Trek's 5 m map. | **SAY IT** | That is why we check 100 m around every site, re-check the demo on Moon Trek's 5 m terrain, and chose a demo (site 210) that passes on both. Every report names the maps it used. **The tool did not predict IM-2.** |
| P5 | **Hourly sampling.** Touchdown is judged at the hour, so a 0.05° margin can change within the hour. | **FIXED in effect** | R1's firm touchdown keeps headline landings at least 0.5° clear, far more than an hour of motion changes. Events are interpolated to the minute. |
| P6 | **The Sun's visible fraction is linear across the disc**, not area-weighted. | **SAY IT** (minor) | The 50% rule (the centre of the disc) is exact. Only partial-Sun power near sunrise and sunset is slightly off. Bilinear terrain also shaves crests by up to 0.017° (ring-crater test). |
| P7 | **2 m is a best fit to NASA's PGDA map.** PGDA also uses LOLA terrain. | **SAY IT** | "It checks the method. The independent checks are JPL Horizons and Skyfield for the sky, and real landers." |
| P8 | **Engine settings are proven within 5° of the pole.** Sites 5–6° out can't be checked at 300 km with the 240 m map. The worst single direction near a sharp crest is 0.27° off on 20 m terrain (99% of directions are within 0.02°). | **SAY IT** | The demo grid is within 0.3° of the pole. Re-run `convergence.py --fine` before the full grid. |
| — | **The sky itself.** | not a risk | JPL Horizons (124 positions within 0.0003°) and Skyfield (0.00032°) agree with our SPICE sky. All real error is in terrain and the lander model. |

### 9.3 Proposed extension: communication-outage planning (not built)

The idea (Nov 13):
- predict direct-to-Earth outages;
- inject an abnormal touchdown;
- plan store-and-forward and battery recovery;
- replay it on IM-1 and IM-2.

Its risks and the fix for each:

| # | Risk | Fix |
|---|---|---|
| C1 | The premise "NASA has a radio-frequency problem" is vague. Our model predicts **line-of-sight** outages from terrain and Earth's motion, not interference or ground-station capacity. | Cite the real causes (DSN oversubscription: NASA Inspector General; IM-1's antenna pointing after it tipped; Earth low on the polar horizon). Claim only the line-of-sight part. |
| C2 | "AEGIS" is already the name of NASA JPL's onboard autonomy software (Curiosity, Perseverance). | Rename it. Check "GHOSTLINK" too. |
| C3 | Store-and-forward is not new: NASA flies delay-tolerant networking (ISS, LunaNet plans). | Claim "store-and-forward scheduled around outages predicted from real terrain", and cite NASA DTN. |
| C4 | Recovery actions need numbers that aren't public (load shedding, data rates, storage). | Every such number is sourced, or a slider the user sets and the page labels as an assumption. |
| C5 | "Reduced solar generation" after a bad touchdown needs panel tilt and direction: new physics. | Inject only what we model: a miss (the 17 points), a tipped lander (mast 0 m), a blocked antenna (Earth margin), a late landing (another hour), a weaker battery or bigger load. |
| C6 | IM-1: our replay shows Earth in view for all 10 days, so we predict **no** outage. Its real problem was pointing. | Say so. An antenna mask is our input, not a prediction. |
| C7 | IM-2: its failure (a crater below map resolution) is what we can't see. | Inject "landed in shadow" as a labelled what-if; never claim the tool foresaw it. |
| C8 | "Our policy would have saved Odysseus or Athena" can't be checked. | Say "how a lander like this could plan around it", never "it would have survived". |
| C9 | IM-1 runs on 240 m terrain; 411 of 1,440 rays leave the map; its death is known to within days. | Every timing claim carries those caveats. |
| C10 | Time: it competes with the submission checklist. | Only after the disclosure, AI statement, Pages, deck and summary are done. |
| C11 | Drift from the challenge (a landing-site navigator). | One demo beat: "and if the landing goes wrong…". |
| C12 | Our rules. | Python only (no physics in the browser), `battery.step` reused, counts rather than a score, every scenario labelled "what-if". |

---

## 10. Judge questions and who answers

| Question | Owner | Answer in one breath |
|---|---|---|
| What did you build at the event? | Ash | "Everything after the tag `pre-event-2026-11-12`: landing at any hour, the battery fix, the lander presets, Horizons and Moon Trek, the ranking explanations, the front end on real data. `git log` shows it." |
| Where did AI write code, and how did you check it? | Ash | "Claude Code wrote much of the code at our request. We checked it with 141 tests, NASA's PGDA maps and JPL Horizons, and every data file says so in its metadata." |
| How does the horizon engine work? | Ash | "For each of 1,440 directions, walk a great circle out to 250 km over 20 m then 240 m terrain, take the highest elevation angle with curvature, and stop early when nothing farther can win." |
| Why 1,440 directions and 250 km? | Ash | "The convergence study: the cheapest settings within 0.02° of the finest in 99% of directions. 200 km misses distant massifs." |
| How do you get the Sun and Earth? | CE 2 | "NASA SPICE, DE421, in LOLA's own Moon frame, every hour 2026–2030; checked against JPL Horizons: 124 positions within 0.0003°." |
| Why do you count Earth if only part of it shows? | CE 2 | "That's NASA's rule in its PGDA maps. The weak-antenna preset needs 2° of clearance instead." |
| What makes a landing safe? | CE 3 | "Power and Earth at touchdown, Earth for half the mission, and the battery never below the reserve, checked from every landing hour." |
| Why no weighted score? | CE 3 | "Weights are opinions. We rank by counts anyone can check: safe days within 100 m, safe days on the point, battery needed." |
| Why a 10 m mast for the demo? | CE 3 | "It's a design requirement our tool found: the same rim spot has zero safe days at 2 m and 315 within 100 m at 10 m, and it passes on NASA's 5 m terrain too." |
| Why is site 131 below 33 at 5 m with more safe days? | CE 3 | "229 days on its exact point, but 6 of the 17 spots within 100 m are steeper than 10°, so a 100 m miss isn't safe. Site 33 keeps 46 days." |
| Why does no 2 m site survive a 100 m miss? | CE 3 | "At the rim either a nearby spot is too steep or a crest blocks the Sun or Earth from 2 m. A 5 m mast clears it: that's a design requirement our tool found." |
| Did your rankings change during the event? Why? | CE 3 / IoT | "Yes, and that's the point of checking. Our risk review found the demo grid's slope came from the 240 m map, not over 100 m as NASA defines it. On the 20 m map five sites were too steep, so we fixed the gate in Step 0 and re-ran. It's in the git log." |
| Where do 700 Wh come from? | IoT | "25 Ah × 28 V, Nova-C-class; 200 W panels from Nova-C's specs; the 50 W load is an estimate from Odysseus's battery life. All labelled." |
| How do you get the slope? | IoT | "Over a 100 m baseline from the finest map at the site, NASA's Artemis gate: under 10°. IM-1 reads 12.2° vs NASA's ~12°." |
| Can I use it without installing anything? | BIT | "Yes: the page, or the one-file offline build. Only hand-set missions need the laptop server." |
| What does the user see first? | BIT | walk through the demo: Your lander → 10 m → Best sites → site 210 → Play the mission → its failsafe card |
| Which NASA data? | Business | "Horizons, Moon Trek and Quickmap from the Resources tab, plus LOLA, SPICE and PGDA." |
| Who benefits? | Business | "CLPS planners picking a site and a landing window; educators showing why the pole is hard; the public." |
| What does it cost to run? | Business | "Nothing: static files. The full grid is minutes on a laptop." |
| Did 2 m come from NASA? | Ash | "No, it's the best fit to NASA's maps. NASA doesn't state its height, so it checks the method." |
| Did your tool predict IM-2? | Ash / CE 3 | "No. Its target was lit. It tipped into a crater about one pixel wide. That's why we check 100 m around every site." |
| No lander has a 10 m mast. | CE 3 | "It's a design option the ranking prices: site 210 is useless at 2 m and the best at 10 m." |
| Why only the south pole? | Business | "It's where Artemis and CLPS are going, and where the Sun and Earth sit on the horizon." |
| What's next? | Business | "Fixed-panel geometry, the full 6° grid, a relay study, rover routes." |

**If you don't know the answer:** say "That's [name]'s step" and hand over. Shared ownership is scored.

---

## 11. The repository

### 11.1 Map

```
horizon/        the engine: reference.py (truth), fast.py (Numba), terrain.py (levels), dem.py (LOLA reader),
                sites.py (sites.csv), synthetic.py (test terrains), __init__.py (settings: the only place)
scripts/        every pipeline step, the validators, the web build and the server (one line each in README.md)
tests/          141 tests: synthetic answers, fast vs reference, conventions, formulas, battery, ranking,
                events, site report, Horizons, Moon Trek, the web build, real-terrain regressions
web/            index.html (the app), assets/ (Moon, PGDA maps), data/ (built by build_web.py; never hand-edit)
docs/           this guide, the UI data contract, the algorithm PDF, the Step 2 notes, the IM-1 replay, the
                horizon engine explained chapter by chapter, the study guide
named_sites.csv notable sites with citations and real landing hours
```

Not in git (too big or private):
- `data/`: LOLA, PGDA, kernels and textures, about 2 GB.
- `out/`: run outputs.
- `Team_Work/`, `CLAUDE.md`, the organizer PDFs.

**The canonical demo outputs:**
- terrain run `out/pipe/horizon`;
- sky `out/pipe6/sky.npz`;
- sites `out/sites/sites.csv` (slope over 100 m);
- presets `out/profiles_r3`.

**Never use `out/demo`.** It predates the great-circle fix.

### 11.2 Timeline

- **Oct 12 – Nov 12, before the event:** the engine, the validation, the pipeline and the first web app.
  - Public on GitHub since Oct 26.
  - Tagged `pre-event-2026-11-12` (`a97aace`).
- **Nov 13, at the event:** 19 commits after the tag:
  - landing at any hour (R7);
  - battery needed from the simulation (R6);
  - lists and stale files (R8, R9);
  - why sentences and the marginal flag (R10);
  - provenance;
  - BIT's v10 and v12 front ends;
  - the one-file offline build;
  - the JPL Horizons validation;
  - the algorithm doc update;
  - lander presets;
  - Moon Trek terrain and photos;
  - headline landings and per-height mission files;
  - the Quickmap button;
  - the ranking explained.

---

## 12. Running it

Setup (Windows, PowerShell, Python 3.14):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests -q                 # 141 pass with data/; the real-data tests skip without it
```

Data goes into `data/` (download links are in README Parts 2, 2b and 6, and Part 9 for Moon Trek).

**The demo, live:**

```
python scripts/serve.py                   # then open http://127.0.0.1:8765/
```

**One site, any hour** (the same report the page plays):

```
python scripts/analyze.py --lat -89.79293 --lon -153.9246 --mast 2 --start 2028-09-02T00 --days 14 --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/analyze/site190.json
```

**Rebuild everything for the page:**

```
python scripts/make_demo_sites.py data/ldem_75s_240m.lbl --slope-dem data/ldem_80s_20m.lbl --out out/sites/sites.csv
python scripts/run_profiles.py --horizon out/pipe/horizon --sky out/pipe6/sky.npz --sites out/sites/sites.csv --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/profiles_r3
python scripts/build_web.py --profiles out/profiles_r3 --region out/region/region_summary.json
python scripts/build_standalone.py        # optional: the one-file offline page
```

`out/sites/sites.csv` holds the 400 demo sites with the slope over 100 m on the 20 m map (risk R2). Its positions match the skylines in `out/pipe/horizon`.

**Checks against NASA:**

```
python scripts/validate_horizons.py --sites named_sites.csv --out out/validate_horizons.json
python scripts/validate_pgda.py data/ldem_75s_240m.lbl data/ldem_875s_20m.lbl data/AVGVISIB_85S_060M_201608.TIF data/AVGVISIB_85S_060M_201608_EARTH.TIF
```

---

## 13. Rules we never break

- **Honesty:**
  - Never hide, squash or redate history.
  - Never present pre-event work as event work.
  - Never claim the tool predicted something it didn't.
- **No weighted score.** Rank by physical counts.
- **No physics in the browser.** Python computes, and the page shows.
- **No synthetic or sample data in the product.** A missing file fails loudly.
- **One implementation per quantity** (e.g. `step()` for the battery, `events.py` for visibility).
- **No NASA logos** in the page, slides or any image. AI-generated images and videos need a visible AI watermark.
- **Conventions never change:**
  - R = 1,737,400 m;
  - θ from map +x, counterclockwise;
  - south polar stereographic;
  - heights relative to R.
- **The data in `web/data/` is built, never edited.**

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Skyline / horizon profile** | H(θ): how high the terrain rises above level in each direction, seen from the lander |
| **Blocker distance** | how far away the terrain that sets the skyline is |
| **Mast** | the height of the panels and antenna above the ground (0, 2, 5 or 10 m) |
| **Clearance** | how far the Sun's centre (or Earth's top) is above the skyline; negative means hidden |
| **DTE** | direct-to-Earth: a radio link straight to Earth, with no relay satellite |
| **Touchdown** | the landing hour: it needs more than half the Sun and some of Earth in view |
| **Safe landing hour / day** | a landing that passes touchdown, Earth for half the mission, and the battery; a day is safe if any of its hours is |
| **Within 100 m** | safe at all 17 points within 100 m of the target |
| **Headline landing** | the one landing per site and height that every number on the page describes |
| **Battery needed / used** | needed: the worst safe landing's drain (e_max − lowest); used: this mission's drain |
| **Bridge** | hours a full battery lasts with no Sun: 11.2 h |
| **Cold soak** | the longest darkness during the mission |
| **Marginal** | the Sun or Earth clears the skyline by under 0.5° at touchdown |
| **Gates** | within 6° of the pole and slope under 10° over 100 m (NASA's Artemis III reference) |
| **Lander preset** | a set of mission requirements (length, Earth margin) for a type of payload; never weights |
| **LOLA** | Lunar Orbiter Laser Altimeter (on NASA's LRO): the terrain heights |
| **SPICE / NAIF / DE421** | NASA's toolkit and data for where bodies are and how they're oriented |
| **PGDA** | NASA Goddard's Planetary Geodesy Data Archive: published sunlight and Earth-visibility maps |
| **CLPS** | Commercial Lunar Payload Services: NASA buying Moon deliveries from companies (IM-1, IM-2, Blue Ghost) |
| **Libration** | Earth's monthly wobble in the lunar sky (about ±6.7°) |
| **Great circle** | the shortest path on a sphere; our rays follow them |
| **Provenance** | the metadata line in every data file stating how it was made, including AI assistance |
