# Ash's Study Guide: CLPS Lunar Mission Browser

NASA Space Apps Challenge 2026 · prepared October 8, 2026

How to use this guide:

- **Part 1, the challenge** (about 10 minutes): what NASA is asking, why it matters, and what other teams are already building.
- **Part 2, the solution** (about 15 minutes): how the whole team's tool works and how we beat the competition.
- **Part 3, your task** (an hour or more, and the part to re-read): the horizon engine, from the geometry to tested code, speed tricks and the plan.
- **Part 4, self-test** (10 minutes): questions to check that you really understand it.

Every number in this guide was either checked against a source (listed at the end) or computed and verified in code.

---

## Part 1: The challenge

### 1.1 The event

- **What:** NASA Space Apps Challenge 2026, theme "The Next Frontier". It's a global 48-hour hackathon.
- **Key dates:**
  - Sept 17: challenge summaries released
  - **Oct 28: full challenge statements and NASA datasets released**
  - Nov 13: submission and judging guides released
  - **Nov 14–15: the hackathon**
  - Nov 16: judging begins
- **Local events can add their own stages.** For example, the Bangladesh event required a public GitHub link and a video by October 7. **Check your local event's rules and deadlines this week.**
- **Rules to remember** (from last year's terms): cite every source you use, and make the solution openly available. Also check the 2026 terms on whether code written before the event is allowed.

### 1.2 Our challenge: "CLPS Lunar Mission Browser"

Official page: <https://www.spaceappschallenge.org/2026/challenges/clps-lunar-mission-browser/>
Subjects: Human Exploration, Moon, Software, Space Exploration.

> Missions to the Moon's south pole face extreme lighting and communication constraints, and planning them takes careful coordination between science and engineering teams. Tools for determining Sun and Earth positions at candidate landing sites exist, but their complicated interfaces make it difficult to evaluate critical information with efficiency. Your challenge is to create an intuitive tool or application that lets mission planners, educators, and the public compare landing sites and dates quickly, visualizing Sun and Earth positions relative to the horizon to assess power generation potential and direct-to-Earth communication windows.

What each phrase tells us:

| Phrase | What it means for us |
|---|---|
| "Tools ... exist, but their complicated interfaces make it difficult to evaluate critical information with efficiency" | **The problem NASA names is usability, not missing science.** Clarity and speed are what they want. Our accurate engine is necessary, but it isn't enough on its own. |
| "intuitive tool or application" | A working software product. Usability will be judged. |
| "mission planners, educators, and the public" | Three audiences: precision for planners, explanations for educators, simplicity for everyone else. |
| "compare landing sites **and dates**" | Comparing both sites and dates is the core feature. |
| "**quickly**" | Answers must be instant, so precompute the heavy work (your horizon engine). |
| "visualizing Sun and Earth positions relative to the horizon" | **The skyline view with the Sun and Earth tracks is a required screen**, and your horizon profile is literally what gets drawn. |
| "power generation potential" | When, and how much, sunlight reaches the panels. |
| "direct-to-Earth communication windows" | The time intervals when Earth is visible, shown as windows on a timeline. |
| "coordination between science and engineering teams" | Results should be easy to share, for example a link or an exported summary. |

**What this changes:** the winning product is a fast, simple core loop: *pick sites and dates → see the skyline with the Sun and Earth → see the power and Earth-contact windows → compare.* Advanced features (battery survival, mast height, landing error) sit behind that loop as extra layers. They must never make it slower or more confusing, because complicated interfaces are exactly the problem NASA wants solved.

### 1.3 What CLPS is, and why this problem is real

**CLPS (Commercial Lunar Payload Services)** is NASA's program for buying deliveries to the Moon from private companies instead of building its own landers. These landers are small, mostly solar-powered, and designed to work for days to about two weeks.

Real missions show exactly why light, communications and terrain decide whether a lander lives:

- **IM-1 Odysseus (February 22, 2024)** landed near Malapert A, tilted about 30° after breaking a leg. The antenna angle reduced its data rate and only one solar panel was lit, but it worked for about a week until the Sun set at its site.
- **IM-2 Athena (March 6, 2025)** aimed for Mons Mouton near the south pole. It landed on its side inside a crater about 20 m wide, in shadow at about −173 °C. The solar arrays produced only about 100 W, not enough to run both the heaters and the high-gain antenna. **Operations ended less than 13 hours after landing.**

The lessons: a 20 m crater can kill a mission, and a lander lives or dies by when and where it gets sunlight and Earth contact.

### 1.4 Why the south pole is hard

- **The Sun stays near the horizon.** The Moon's axis is tilted only about 1.5° to the Sun's path, so at the pole the Sun stays within about ±1.5° of level. It crawls all the way around the horizon once every ~29.5 days.
- **Earth bobs up and down in one direction.** The Moon always shows Earth the same face, so Earth doesn't go around the sky. It stays in one narrow direction and bobs about ±6.7° (this wobble is called libration). NASA describes it as visible for two weeks, then hidden for two weeks.
- **Both stay low.** NASA says the Sun and Earth rise only about 2–7° above the horizon, so ordinary crater rims block them.
- **Light varies hugely from place to place.** Some crater floors never see the Sun (permanently shadowed regions). A site on the rim of Shackleton crater is sunlit about 240 days a year, with its longest darkness only about 1.5 days (Mazarico et al.).

> **Key idea:** a landing site is a point in time, not just a point on a map.

### 1.5 NASA's reference requirements (Artemis III)

From NASA's Artemis briefing prepared for Space Apps:

- Land within 6° latitude of the south pole.
- Slope under 10° over 100 m.
- **Direct-with-Earth communication. Assume no relay is available.**
- Lighting for the surface and for the approach.
- Land within 100 m of the target.

### 1.6 The competition is already moving

Several teams already have public repositories for this exact challenge. According to their READMEs:

| Team / repo | What they claim to have |
|---|---|
| LunaHorizon | Horizons ray-traced to 260 km with curvature; LOLA 80 m and 240 m maps plus 5 m and 20 m windows near sites; a "Window Finder"; an optional relay; runs in the browser |
| Sightline (Bangladesh) | SPICE plus a 3D view; their plan uses 0.25° azimuth steps, 200 km range and exact curvature |
| lunar-horizon-clps-browser (Málaga) | Slope traffic-light scale, 360° horizon, 30-day timeline, 0–100% suitability index, "top 5 sites" autopilot |
| lunarsite-compass | Hour-by-hour sunlight, direct-to-Earth comms, slope and more |

**What this means:** a horizon ray-tracer with a 30-day timeline and a top-5 list is the *baseline*, not a winner. The approach is right (it is literally what the challenge asks for), so we win on **depth, correctness and clarity**, not on a different idea. Notice their stated limitations, for example "one time per day, Sun as a point, fixed 2 m height, terrain outside the map ignored". Those are exactly the things we do better.

---

## Part 2: The solution

### 2.1 The core idea in one paragraph

Stand at a site and look around 360°. The terrain's top edge is a **skyline**, the horizon profile H(θ): for each direction θ, how high the terrain blocks the sky. The skyline never changes because the terrain doesn't move; only the sky moves. So we compute each site's skyline **once**. After that, any hour is a cheap check: is the Sun above the skyline in the Sun's direction, and is Earth above the skyline in Earth's direction?

### 2.2 Why this approach and not another

- **Not machine learning.** Visibility has one exact geometric answer. The only way to make training labels is to run this algorithm, so a model would just be a worse copy of it.
- **Not a hardware relay network.** NASA's own requirement says to assume no relay, and placing beacons would need this exact analysis anyway.
- **Not checking the Sun directly every hour.** That means walking over the terrain once per hour: 8,760 walks per site for a year. The skyline needs 360–1,440 walks once, after which every hour is a lookup.

### 2.3 The pipeline

| Step | What it does | Owner |
|---|---|---|
| 0 | Prepare terrain: load LOLA heights, crop, slope map, candidate site grid | IoT |
| **1** | **Horizon profile for every site (and mast height)** | **Ash** |
| 2 | Sun and Earth direction and height above the horizon for every site and hour (SPICE) | CE 2 |
| 3 | Visibility each hour: is the Sun or Earth above the skyline? | CE 3 |
| 4 | Score, rank, battery survival, landing-error robustness, best dates | CE 3 (+ IoT for battery) |
| 5 | Prove it's right: tests and comparison with NASA's maps | Ash (tests), Business (NASA maps) |
| — | Web app: map, timelines, comparison, explanations | BIT |
| — | Pitch, video, project page, sources | Business |

### 2.4 Steps 3–4 in formulas (what your output feeds)

Here `az` and `el` are the direction and height above level of the Sun (☉) or Earth (⊕), and `H(...)` is your horizon profile interpolated between azimuths. The Sun and Earth are discs, not points: seen from the Moon, the Sun's radius is r☉ ≈ 0.27° and Earth's is r⊕ ≈ 0.95° (0.90–1.02° depending on distance).

```
fraction of Sun visible:   s(t) = clamp((el☉ − H(az☉) + r☉) / (2·r☉), 0, 1)
Earth visible:             e(t) = el⊕ + r⊕ > H(az⊕)      (any part of the disc, NASA's rule)
power + comms together:    b(t) = (s(t) > 0.5) and e(t)
score:                     S = w1·f_sun + w2·f_earth + w3·f_both − w4·(longest dark gap / T)
battery:                   E(t+1) = min(E_max, E(t) + (P_panel·s(t) − P_load)·Δt), survive if E ≥ E_min always
landing-error robustness:  S_robust(p) = min of S over all points within 100 m of p
```

### 2.5 How we beat the baseline

**First, nail the core loop from 1.2.** It must be fast, clear, and usable by someone who has never heard of SPICE. Everything below is a layer on top of it.

1. **Power and comms at the same time**, not separately. In our toy example, a site had sunlight 36% of the month and Earth 41%, but both together only 19%.
2. **A survival verdict.** "This lander survives the 30-day mission" or "dies on day 12." That's the IM-2 lesson.
3. **Robustness to landing error.** Score the worst point within 100 m, and use high-resolution terrain near the site. IM-2 died in a 20 m crater.
4. **Mast-height recommendation.** Mazarico et al. note that small height gains can substantially improve illumination at some sites. We tell the user the lowest mast that meets their targets.
5. **"Why" explanations for educators and the public.** For example: "No sunlight on day 12 because the rim 8 km away in direction 140° blocks it." This comes straight from your **blocker distance** output (Part 3).
6. **Proven accuracy.** We show passing tests, a match with NASA's published maps, and that we reproduce the Shackleton-rim facts.
7. **Instant and intuitive.** Everything heavy is precomputed, comparison is side by side, and the language is plain.

---

## Part 3: Your task, the horizon engine

### 3.1 Your job in one sentence

For every candidate site and mast height, compute the **horizon elevation H(θ)** in every direction θ, plus the **distance to the terrain that blocks it**. Do it correctly, fast enough to cover the whole region, and prove it with tests.

**Your skyline is not just intermediate data.** The challenge asks to visualize the Sun and Earth relative to the horizon, so your H(θ) is drawn on screen in the main view. It must look right as well as be right.

**"Quickly" affects your design.** There are two ways to serve whatever site a user clicks:

1. Snap to the nearest precomputed site. This is simple, but needs a fine enough grid in the areas people actually look at.
2. Compute that site's skyline on demand in under a second.

Start with snapping. On-demand is a stretch goal that your fast single-site version makes possible; another team reports about 2 million samples in under 0.1 s for one site in the browser.

**Definition of done:**

- [ ] Passes the smooth-Moon, single-cone and ring-crater tests (section 3.9).
- [ ] Results stop changing (within about 0.02°) when range, azimuth count or step size are increased.
- [ ] Runs on the full candidate grid at all mast heights within a few hours, ideally much less.
- [ ] Produces `horizon.npy`, `blocker.npy`, `complete.npy` and `horizon_meta.json` in the agreed format (section 3.10).
- [ ] Flags every ray that left the terrain map before reaching full range.
- [ ] Is documented well enough for you to explain it to a judge in 60 seconds.

### 3.2 The geometry, from first principles

**Setup.** Treat the Moon as a sphere of radius **R = 1,737.4 km**. LOLA heights are measured relative to this sphere, so a point with height z sits at distance R + z from the Moon's centre. The observer (solar panel or antenna) sits at height h0 + m, where h0 is the ground height at the site and m is the mast height.

**Exact elevation angle.** Take a terrain point at surface distance d from the site. Seen from the Moon's centre, it is φ = d / R radians away from the observer. Put the observer at the top of the circle and measure from there:

```
horizontal = (R + z) · sin φ
vertical   = (R + z) · cos φ − (R + h0 + m)
α          = atan2(vertical, horizontal)          ← exact for a sphere
H(θ)       = max of α over all samples along direction θ
```

**The common approximation**, valid when d is much smaller than R:

```
α ≈ atan( (z − h0 − m − d²/2R) / d )
```

Here d²/2R is how far the curved surface drops below a flat line. **Use the exact form.** It costs nothing, because cos φ and sin φ depend only on d, so you compute them once for all rays and all sites.

**Why curvature matters** (target 1,000 m above the site; all values computed and checked):

| Distance | Curvature drop | Error if you ignore curvature | Error of the approximation |
|---|---|---|---|
| 1 km | 0.3 m | 0.03° | 0.016° |
| 5 km | 7.2 m | 0.09° | 0.006° |
| 20 km | 115 m | **0.33°** | 0.002° |
| 50 km | 720 m | **0.83°** | 0.0006° |
| 100 km | 2,878 m | **1.65°** | 0.0005° |
| 200 km | 11,512 m | **3.30°** | 0.003° |

The Sun moves within only ±1.5° of level, so ignoring curvature would be a disaster. The approximation is fine but not perfect, which is another reason to use the exact form.

**Mast height.** Raising the observer by m lowers the angle to a blocker at distance d by about m / d radians. That means near blockers matter most:

| Mast | Blocker 1 km away | 2 km | 10 km |
|---|---|---|---|
| 2 m | 0.115° | 0.057° | 0.011° |
| 10 m | **0.573°** | 0.286° | 0.057° |

A 10 m mast can buy more than half a degree against a nearby rim. That's twice the Sun's radius, and it can be the difference between light and dark.

**H can be negative.** On a high peak, everything around may be below level. Even on a perfectly smooth Moon, an observer 2 m up sees the horizon 0.087° below level, and 10 m up sees it 0.194° below. **Never clamp H to 0.** A Sun at −0.1° can still be visible from a peak.

### 3.3 The data you walk over

**LOLA** (Lunar Orbiter Laser Altimeter) is on NASA's Lunar Reconnaissance Orbiter. It fires laser pulses and times the reflections to measure surface heights, and it works in total darkness. The poles are its best-mapped areas.

**Where to get it:**

- **PDS Geosciences Node**, polar gridded height maps, for example `LDEM_75S_240M` and `LDEM_80S_80M`: <https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/>
- **NASA Goddard PGDA**, higher-resolution south-pole maps (down to a few metres near some sites) and NASA's illumination maps for validation: <https://pgda.gsfc.nasa.gov/>

**Read each product's label file before using it.** Heights are often stored as integers with a scale factor and offset. Get these wrong and everything is wrong.

**Map projection.** The polar products use a **polar stereographic** projection: a flat x/y grid in metres centred on the pole. Two useful properties:

- **It preserves angles locally** (it's "conformal"), so directions measured on the map are true directions at each point.
- **Distances stretch slightly.** At 84°S (the edge of NASA's 6° zone) the scale factor is 1.0027, so distances are off by under 0.3%. Over the distances we march, straight map lines are also very close to the true shortest paths over the surface. Both effects are negligible for us; mention them as known approximations.

**Memory forces multi-resolution.** The terrain must cover the site area **plus** the full look-out range on every side:

| Area | 240 m grid | 80 m grid | 20 m grid | 5 m grid |
|---|---|---|---|---|
| Sites within 6° + 200 km margin | 0.04 GB | 0.36 GB | **5.8 GB** | 93 GB |
| Sites within 3° + 200 km margin | 0.02 GB | 0.21 GB | 3.4 GB | 54 GB |

(float32 heights.) So: **coarse terrain (80 m or 240 m) for the far field, fine terrain (20 m or 5 m) only near the sites.** Fine terrain matters most close by, because one pixel there covers a bigger angle:

| One pixel of... | at 10 km | at 100 km |
|---|---|---|
| 20 m | 0.115° | 0.011° |
| 80 m | 0.458° | 0.046° |
| 240 m | 1.375° | 0.138° |

**Direction convention (the most likely bug in the whole project).** At the south pole every direction is "north", so compass bearings don't work. We measure **azimuth θ from the map's +x axis, counterclockwise, 0–360°**. Direction θ means moving by (cos θ, sin θ) in map x/y. In the grid array, +y means a *smaller* row number, because row 0 is the top of the image.

### 3.4 The algorithm, with every trick

```
PRECOMPUTE ONCE (shared by every site and every ray):
  d[k]                      distances along a ray, k = 0..K−1  (schedule below)
  cosφ[k], sinφ[k]          with φ = d[k] / R
  cosθ[j], sinθ[j]          for every azimuth j = 0..N−1

FOR EACH SITE s  (in parallel):
  r_obs = R + z(site) + mast
  A     = R + max(z_max, z(site) + mast)      # tallest possible terrain, for early exit
  FOR EACH AZIMUTH j:
    best = −∞ ; best_k = none
    FOR k = 0..K−1:
      bound = (A·cosφ[k] − r_obs) / (A·sinφ[k])   # best tan any farther terrain could give
      IF best ≥ bound: BREAK                       # nothing farther can beat it
      x = x_site + d[k]·cosθ[j] ;  y = y_site + d[k]·sinθ[j]
      z = bilinear(DEM level for d[k], x, y)       # coarser level when far away
      IF z is outside the map: mark incomplete; BREAK
      t = ((R+z)·cosφ[k] − r_obs) / ((R+z)·sinφ[k])   # tan of the elevation angle
      IF t > best: best = t ; best_k = k
    H[s, j] = atan(best) in degrees ;  D[s, j] = d[best_k]
```

Four details make this both correct and fast:

1. **Compare tangents, not angles.** atan only ever increases, and the horizontal part is always positive, so the largest tangent is the largest angle. That's one atan per ray instead of one per sample.
2. **Early exit is exact, not a guess.** The bound uses the tallest terrain anywhere (`z_max`). Its derivative is d(bound)/dφ = ((r_obs/A)·cos φ − 1) / sin²φ, which is negative because r_obs ≤ A. So the bound only *decreases* with distance, and once your current best beats it, no farther point can win. It helps most for sites deep in craters, where a high rim is found early.
3. **Step schedule:** `step = max(pixel/2, κ·d)`. Steps are half a pixel near the site and grow in proportion to distance far away, which keeps the angular resolution roughly constant. Steps per ray to 200 km on a 20 m grid: **κ = 0.002 → 2,347 steps; 0.001 → 3,998; 0.0005 → 6,607.**
4. **Blocker distance D(θ):** keep `best_k`. It costs nothing and powers the "why" explanations, mast reasoning and validation.

**Starting parameters, then test them:**

| Parameter | Start with (development) | Final: test and choose |
|---|---|---|
| Azimuths N | 720 (0.5°) | 1,440 (0.25°); check the difference |
| Range d_max | 150 km | 100 / 150 / 200 / 250 km, until changes are under ~0.02° |
| Step factor κ | 0.002 | 0.001, 0.0005 |
| First step | half a pixel | — |
| Terrain | 240 m everywhere | 80 m far field + 20 m (or 5 m) near the sites |
| Mast heights | 0, 2, 5, 10 m | Sun at panel height, Earth at antenna height |

### 3.5 The three ways to miss a peak

1. **Gaps between azimuths.** Neighbouring rays spread apart with distance, so a narrow peak between them is missed:

   | Distance | 1° spacing | 0.5° | 0.25° |
   |---|---|---|---|
   | 10 km | 175 m | 87 m | 44 m |
   | 50 km | 873 m | 436 m | 218 m |
   | 100 km | 1,745 m | 873 m | 436 m |
   | 200 km | 3,491 m | 1,745 m | 873 m |

   **Fix:** use more azimuths, and test how much H changes when you double them.
2. **Steps longer than the terrain features**, which jump over a sharp peak. **Fix:** never step farther than about one pixel of the terrain level in use (the κ·d rule plus multi-resolution handles this).
3. **Terrain finer than the map.** A 20 m crater does not exist in an 80 m map. **Fix:** fine terrain near the sites. For the far field, use a **max-pyramid**: each coarse pixel stores the *maximum* height of the fine pixels it covers, not the average. A max-pyramid never hides a peak. It can only make the horizon slightly too high, which means predicting slightly *less* light, never more. That's the safe direction for mission planning.

### 3.6 Reference implementation (tested)

This is plain NumPy for **one site**: correct and readable, but not fast. It's your ground truth for checking the fast version. Both tests below pass.

```python
import numpy as np

R = 1_737_400.0  # m, radius of the LOLA reference sphere


def step_schedule(pixel, d_max, kappa=0.001):
    """Distances along a ray: half-pixel steps near the site, steps ~ kappa*d far away."""
    d = [pixel / 2]
    while d[-1] < d_max:
        d.append(d[-1] + max(pixel / 2, kappa * d[-1]))
    return np.array(d)


def bilinear(dem, col, row):
    """Sample dem at fractional (col, row). NaN outside the grid."""
    nr, nc = dem.shape
    c0 = np.floor(col).astype(int)
    r0 = np.floor(row).astype(int)
    ok = (c0 >= 0) & (r0 >= 0) & (c0 < nc - 1) & (r0 < nr - 1)
    c0 = np.where(ok, c0, 0)
    r0 = np.where(ok, r0, 0)
    fc, fr = col - c0, row - r0
    z = (dem[r0, c0] * (1 - fc) * (1 - fr) + dem[r0, c0 + 1] * fc * (1 - fr)
         + dem[r0 + 1, c0] * (1 - fc) * fr + dem[r0 + 1, c0 + 1] * fc * fr)
    return np.where(ok, z, np.nan)


def horizon_profile(dem, pixel, col0, row0, mast, d_max, n_az=1440, kappa=0.001):
    """Horizon elevation H (deg), blocker distance (m) and completeness flag for one site."""
    theta = np.arange(n_az) * (2 * np.pi / n_az)        # from map +x, counterclockwise
    d = step_schedule(pixel, d_max, kappa)
    phi = d / R                                         # central angle to each sample
    cols = col0 + np.outer(np.cos(theta), d) / pixel
    rows = row0 - np.outer(np.sin(theta), d) / pixel    # map +y = smaller row index
    z = bilinear(dem, cols, rows)
    r_obs = R + float(bilinear(dem, np.array(col0), np.array(row0))) + mast
    r_pt = R + z
    up = r_pt * np.cos(phi) - r_obs                     # height above the observer's level
    out = r_pt * np.sin(phi)                            # horizontal distance
    ratio = np.where(np.isnan(z), -np.inf, up / out)    # tan(angle); max ratio = max angle
    k = np.argmax(ratio, axis=1)
    H = np.degrees(np.arctan(ratio[np.arange(n_az), k]))
    complete = ~np.isnan(z[:, -1])                      # False if the ray left the DEM
    return H, d[k], complete
```

**Tests** (20 m pixels, a 40 km × 40 km map, site at the centre):

```python
# Test 1: smooth Moon, observer 2 m up -> the same dip in every direction
dem = np.zeros((2001, 2001))
H, D, ok = horizon_profile(dem, 20.0, 1000, 1000, mast=2.0, d_max=15_000)
expected = -np.degrees(np.arccos(R / (R + 2.0)))       # -0.08694 deg
assert np.allclose(H, expected, atol=1e-4)

# Test 2: one cone, peak P = 1000 m at L = 10 km in direction 0 (map +x)
# expected = degrees(atan2((R+P)*cos(L/R) - R, (R+P)*sin(L/R)))  = 5.544056 deg
```

Results when I ran it:

```
smooth: expected -0.08694  got min -0.08694 max -0.08694  blocker ~2640 m (tangent 2636 m)
cone:   expected 5.544056  got 5.544056  blocker 10000 m
```

The smooth-Moon blocker lands at about 2.64 km, matching the theoretical tangent distance √(2Rh) = 2,636 m. This also proves the range must reach past that distance. With this plain NumPy version, one site at 1,440 azimuths out to 15 km took 0.27 s. The full-range, many-site version needs the speed work below.

### 3.7 Making it fast (your playground)

**Cost model:** sites × azimuths × steps. For example, 10,000 sites × 1,440 azimuths × 2,347 steps = **3.4 × 10¹⁰ terrain samples** per mast height. At 40,000 sites it's 1.35 × 10¹¹. The output is about 58 MB per mast height for 10,000 sites (float32).

In order of payoff:

1. **Numba:** `@njit(parallel=True)` with `prange` over sites. Each site is independent, so it scales across all CPU cores. Write plain loops exactly like the pseudocode in 3.4.
2. **Precomputed tables:** d, cos φ, sin φ, cos θ and sin θ, computed once for everything.
3. **Tangents instead of atan:** one atan per ray (see 3.4).
4. **Early exit:** exact, and big savings for crater sites.
5. **Max-pyramid multi-resolution:** coarse far-field samples are cheaper and touch less memory.
6. **float32 terrain:** half the memory traffic, and still plenty of precision. Do the geometry in float64, because R is about 1.7 × 10⁶ m and the differences are a few metres.
7. **Cache locality:** march the rays of one site together, since neighbouring rays touch nearby terrain.
8. **Benchmark first, then optimise.** Time 1, 10 and 100 sites; compute samples per second; extrapolate to the full grid. A GPU (Numba CUDA or CuPy) is an option only if the CPU version is too slow.

Your VLSI and embedded mindset fits here: fixed precomputed tables, a tight inner loop, and stopping as early as is provably safe.

### 3.8 Edge cases

- **The ray leaves the map** before full range: stop, set `complete = False`, and make sure the terrain margin is at least the full range.
- **Missing terrain values (no-data holes):** skip the sample and count them. Flag the site if there are many.
- **Negative horizons:** valid on peaks. Never clamp.
- **Sites near the map edge:** won't have complete horizons. Exclude them or extend the terrain.
- **Panel versus antenna height:** the Sun check uses the panel height and the Earth check uses the antenna height. Your mast list covers both.
- **The site's own pixel:** start at half a pixel out. Nearby slopes are naturally included.

### 3.9 Proving it's right (test list)

1. **Smooth Moon:** H = −arccos(R / (R + h)) in every direction (done above).
2. **Single cone:** exact angle in its direction, and the blocker distance equals the cone's distance (done above).
3. **Ring crater:** observer at the centre of a circular rim of height P and radius L. Every direction should give the same H, equal to the cone formula. This catches direction-convention and interpolation bugs. When I ran it (20 m grid, sharp 1 km rim at 10 km), the directions along the grid axes were exact, and diagonal ones came out up to 0.017° low. That's because bilinear interpolation shaves sharp crests that fall between grid points, so pass the test at about 0.02°. It's also a real lesson: interpolation slightly *under*-estimates sharp peaks, while a max-pyramid slightly *over*-estimates them. Know which way each error goes.
4. **Convergence:** increase range, azimuth count and step density until the change is under ~0.02°. Record the chosen values in `horizon_meta.json`.
5. **Resolution:** compare 80 m against 20 m terrain at some sites. The difference shows how much fine terrain matters near the site.
6. **Fast version against the reference:** the Numba version must match the NumPy reference within 1e-6° on random sites.
7. **Against NASA (with the team):** average our sunlight over a long period and compare with NASA's illumination maps, which are averaged over 18.6 years with hourly steps. The same sunny ridges must stand out, and a Shackleton-rim site should come out at roughly 240 sunlit days a year with about 1.5 days of longest darkness.
8. **Speed:** a benchmark number for your slides ("samples per second, full grid in N minutes").

### 3.10 Interfaces: what you hand to the team

```
horizon.npy        float32 [n_sites, n_masts, n_az]   horizon elevation, degrees
blocker.npy        float32 [n_sites, n_masts, n_az]   distance to the blocking terrain, metres
complete.npy       bool    [n_sites, n_masts, n_az]   ray reached full range
horizon_meta.json  {"n_az": 1440, "azimuth": "deg from map +x, counterclockwise",
                    "masts_m": [0, 2, 5, 10], "d_max_m": ..., "kappa": ...,
                    "R_m": 1737400, "dem_files": [...], "sites_file": "sites.csv"}
```

Function signature to agree on: `horizon_profile(dem_levels, site_x, site_y, mast) -> (H, D, complete)`.

**Make CE 2's Sun and Earth directions match your convention.** SPICE gives a local azimuth: clockwise from local north, where at the south pole "north" means toward the equator. To convert to map azimuth:

1. For each site, project the site and a point slightly north of it onto the map (pyproj, same projection as the terrain).
2. The angle of that short vector in map x/y is β, the direction of local north on the map.
3. Map azimuth: **θ = β − local azimuth**. The projection preserves angles, so this rotation is exact.
4. Elevation needs no change, *as long as* SPICE's "level" is perpendicular to the Moon's radius, which matches our sphere.

Run one joint test: put a fake "Sun" exactly behind your test cone and confirm the pipeline says "hidden".

### 3.11 Your plan to November 14

| When | Goal |
|---|---|
| **Oct 8–14** | Run the reference code; write the ring test; load a real 240 m LOLA map (read the label!); plot one real horizon near Shackleton and check it looks plausible. Check your local event's rules and deadlines. |
| **Oct 15–21** | Numba version with early exit and the step schedule; convergence tests; benchmark; first `horizon.npy` for a small site grid handed to CE 3. |
| **Oct 22–28** | Multi-resolution (80 m far + 20 m near, max-pyramid); blocker distance; mast heights. **Oct 28: read the full statement and adjust.** |
| **Oct 29 – Nov 8** | Full-region batch run; NASA-map comparison with the team; fix discrepancies. |
| **Nov 9–13** | Freeze the engine; full dry run of the pipeline; one slide on "how the engine works" plus test results. |
| **Nov 14–15** | Final runs; help integration; answer the judges' technical questions. |

If the rules require code to be written during the event, use these weeks for learning and quick test versions, then write the final engine during the hackathon. With this guide, you'll be fast.

### 3.12 What to learn (in order)

1. **NumPy broadcasting**, to read and extend the reference code.
2. **Numba** (`@njit`, `parallel=True`, `prange`) for the fast engine.
3. **rasterio** and reading PDS label files, to load LOLA terrain correctly.
4. **pyproj** with polar stereographic, for site coordinates and the azimuth conversion.
5. **Bilinear interpolation** and **image pyramids**, for sampling and multi-resolution.
6. **SPICE basics** (frames, local azimuth and elevation), enough to agree conventions with CE 2.
7. Read: NASA's PGDA illumination page, the Mazarico et al. abstract, and NASA's Artemis briefing for Space Apps.

---

## Part 4: Self-test

Answer these out loud before checking the answers.

1. Why can a farther mountain block the Sun when a nearer one doesn't?
2. Why compute the skyline once instead of checking the Sun every hour?
3. What happens at 100 km if you ignore curvature?
4. Why does Earth visibility depend on only one direction?
5. Can H be negative? Should you clamp it to 0?
6. Why is a max-pyramid "safe" for mission planning?
7. Why is the largest tangent the same as the largest angle?
8. When can a ray stop early, and why is that exact?
9. Why does mast height matter more for near blockers?
10. Which convention mismatch would silently break everything?

**Answers.**
1. The angle depends on height ÷ distance; a farther but much higher peak can make a bigger angle.
2. The terrain never changes. 1,440 rays once versus 8,760 walks per site per year, and new dates cost almost nothing.
3. About a 1.65° error, which is more than the Sun ever rises above level at the pole (about 1.5°).
4. Earth stays in one narrow direction and only moves up and down (libration).
5. Yes, it can be negative on peaks. Never clamp: a Sun slightly below level can still be visible.
6. It can only make the horizon too high, so it predicts less light, never more.
7. atan only increases, and the horizontal part is positive.
8. When the current best tangent beats the tallest-possible-terrain bound. That bound only decreases with distance, so nothing farther can win.
9. The angle change is about mast height ÷ distance.
10. The azimuth convention between your horizon and CE 2's Sun and Earth directions.

---

## Glossary

| Term | Meaning |
|---|---|
| CLPS | Commercial Lunar Payload Services: NASA buying Moon deliveries from companies |
| LOLA | Lunar Orbiter Laser Altimeter, the laser that mapped lunar heights |
| LRO | Lunar Reconnaissance Orbiter, the spacecraft carrying LOLA |
| DEM | Digital elevation model, a grid of terrain heights |
| PDS / PGDA | NASA's Planetary Data System / Goddard's Planetary Geodesy Data Archive |
| SPICE | NASA/JPL toolkit for positions, orientations and times of bodies in space |
| Azimuth θ | Direction around the site (ours: from map +x, counterclockwise) |
| Elevation | Angle above the local level |
| Horizon profile H(θ) | Skyline: terrain elevation angle in each direction |
| Libration | The Moon's apparent wobble that makes Earth bob ±6.7° at the pole |
| PSR | Permanently shadowed region, a crater floor that never sees the Sun |
| Polar stereographic | Flat map projection centred on the pole; preserves angles |
| Bilinear interpolation | Estimating a value between four neighbouring grid points |
| Max-pyramid | Coarser terrain copies where each pixel stores the maximum of the pixels it covers |
| Direct-to-Earth (DTE) | Radio link straight to Earth with no relay |

---

## Sources

- [NASA Space Apps 2026: CLPS Lunar Mission Browser](https://www.spaceappschallenge.org/2026/challenges/clps-lunar-mission-browser/)
- [NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/)
- [Registration open for Space Apps 2026: key dates (Astrobiology)](https://astrobiology.com/2026/09/04/registration-is-now-open-for-the-2026-nasa-space-apps-challenge/)
- [Space Apps 2026 schedule incl. Nov 13 guides (Internshala listing)](https://internshala.com/competitions/nasa-international-space-apps-challenge-2026-registration/)
- [Sightline team plan (horizon parameters and performance figures)](https://raw.githubusercontent.com/WarRinOP/sightline/main/docs/MASTER_PLAN.md)
- [NASA Space Apps participant terms](https://spaceappschallenge.org/legal)
- [NASA, Artemis Overview for the 2025 International Space Apps Challenge (NTRS)](https://ntrs.nasa.gov/api/citations/20250009323/downloads/ArtemisOverview2025IntSPAPPSChallenge.pdf)
- [NASA Goddard PGDA: Lunar Polar Illumination](https://pgda.gsfc.nasa.gov/products/69)
- [Mazarico et al., Illumination conditions of the lunar polar regions using LOLA topography (NTRS)](https://ntrs.nasa.gov/citations/20120010094)
- [PDS Geosciences: LOLA polar gridded data](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/)
- [IM-2 (Wikipedia)](https://en.wikipedia.org/wiki/IM-2)
- [IM-1 (Wikipedia)](https://en.wikipedia.org/wiki/IM-1)
- [NASA NAIF: SPICE toolkit](https://naif.jpl.nasa.gov/naif/)
- [SpiceyPy](https://github.com/AndrewAnnex/SpiceyPy)
- Other teams' repos: [LunaHorizon](https://github.com/samuelakosaonyejekwe/lunahorizon) · [Sightline](https://github.com/WarRinOP/sightline) · [lunar-horizon-clps-browser](https://github.com/rafaa-sf/lunar-horizon-clps-browser) · [lunarsite-compass](https://github.com/partofcosmos-site/lunarsite-compass)
