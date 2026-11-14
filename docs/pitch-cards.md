# Pitch cards: the 7-minute script and each member's 60 seconds

**Who this is for:** all six of us, for the live judging (7 minutes of pitch, then 3 minutes of Q&A). Read your own card out loud twice. Judges score "shared ownership of answers": when a question is about your step, you answer it. The full detail is in `docs/team-guide.md`.

## The 7-minute script

| Time | Who | What | On screen |
|---|---|---|---|
| 0:00–0:40 | Business | **The problem.** Near the Moon's south pole the Sun never rises more than about 1.5° above the horizon, and Earth hangs low in one direction. A hill 10 km away decides whether a lander has power. IM-1 tipped over and lasted about a week; IM-2 landed on its side in shadow and ended within 13 hours. Planners need to know **where and when** a landing gets sunlight and a link home. | slide 2 |
| 0:40–3:30 | BIT drives, Ash narrates | **Live demo** (open `index.html#site=210&mast=10`): (1) "Your lander": Nova-C class, 14 days. (2) **Height 10 m → Best sites → site 210, the Shackleton rim.** Read "Why #1": 315 safe days even if we miss by 100 m. (3) Switch to **2 m**: the same spot has zero safe days. "A landing site is a point in time *and* a height." (4) **Play the mission**: the real horizon, the Sun circling, Earth low, the countdowns, the battery. (5) **Failsafe card**: it can land up to 176 h late, all 17 points within 100 m are safe, Earth is in view at landing, mid-mission and end, and it survives on half the battery, at best. | the page |
| 3:30–5:00 | Ash, then CE 2 | **How it works.** Ash: "For each of 1,440 directions we walk the terrain out to 250 km and take the highest angle, curvature included." CE 2: "NASA SPICE gives the Sun and Earth every hour from 2026 to 2030, in LOLA's own Moon frame." | slide 4 |
| 5:00–6:15 | CE 3, then IoT | **Evidence.** CE 3: "Every landing hour is tested against NASA's Artemis rules, and we rank by counts, not weights." IoT: "The battery is a Nova-C-class model with sources; survival is an upper bound." Then the numbers: **0.0003° against NASA JPL Horizons, r = 0.92 against NASA's sunlight map, 151 tests, and the demo passes on NASA Moon Trek's 5 m terrain too.** | slide 5 |
| 6:15–7:00 | Business | **Honest limits, AI use, impact, next.** "Built before and during the event (git tag); written with AI, verified by tests and NASA checks. It costs nothing to run. Next: fixed-panel geometry, newer 5 m terrain, traverse planning." | slides 6–7 |

**If a judge asks "is it only one crater?":**
1. Open the **"The region"** tab (or the link `index.html#tab=region`): all 2,436 sites within 6°, the best at your height.
2. Then, live in **Plan your own mission** (local server):
   - latitude −87.04745, longitude −24.1866;
   - 2 m height;
   - landing 2027-11-05 06:00 UTC, 14 days.
3. That's site 422, the best 2 m site region-wide. It plays as safe, with the Sun 2.16° and Earth 0.54° above the skyline at touchdown.

**If the laptop dies:** the GIF in `docs/media/` shows the demo path, and every number is in the deck.

## Ash: the horizon engine (Step 1)

**60 seconds:** "The lander sees the Sun only if it is above the real horizon. For each of 1,440 directions, a quarter of a degree apart, we walk outward along the Moon's surface to 250 km. Within 40 km we use NASA LOLA's 20 m map; beyond it, the 240 m map. At each step we compute the exact elevation angle with the Moon's curvature, and the highest one is the horizon in that direction. Ignore curvature and you are 1.65° wrong at 100 km, more than the Sun's whole range. The engine compares tangents instead of angles and stops a ray as soon as nothing farther can be higher, so it takes about 3.5 ms per site. A convergence study chose these settings: every site's skyline is within 0.02° of the finest settings in 99% of its directions."

- **Tests:** a smooth Moon gives −0.08694° exactly; a cone gives its exact angle; the fast engine matches a plain reference engine to 1e-6°.
- **The limit to admit first:** terrain finer than 20 m is invisible to it. Site 33 passes on our 20 m map but fails on NASA Moon Trek's 5 m map, which is why the demo is site 210, which passes on both.

## CE 2: the Sun and Earth (Step 2)

**60 seconds:** "We use NASA's SPICE toolkit with the DE421 ephemeris to place the Sun and Earth in each site's sky every hour from 2026 to 2030, in the same Moon frame as the LOLA terrain. We convert SPICE's compass azimuth to the team's map direction with one formula, theta = beta − A, pinned by a test. We also store the apparent radius of each disc every hour: about 0.27° for the Sun, 0.95° for Earth. We checked 124 positions against NASA JPL Horizons, the tool in the challenge's Resources tab: every one is within 0.0003°. A second library, Skyfield, agrees to 0.00032°."

- **The limit:** effectively none on the sky. All the real error is in terrain and the lander model.

## CE 3: safe landings and the ranking (Steps 3–4)

**60 seconds:** "A landing hour is safe when three things hold:
1. at touchdown more than half the Sun and some of Earth are above the skyline;
2. Earth stays in view for at least half the mission (no relay, NASA's rule);
3. the battery never drops below its reserve.

We test all 43,489 landing hours from 2026 to 2030. A lander can miss by 100 m, so a date only counts if it is safe at 17 points within 100 m, and each point must be under 10° of slope. Sites are ranked by safe days within 100 m, then safe days on the exact point, then battery needed. There is no weighted score, and every rank says in words why it is there. Tonight's failsafe card adds what a late landing, a miss or half the battery would do."

- **The limit:** "Earth for half the mission" is a requirement we chose and state. The third ranking key, battery needed, almost never decides a rank.

## IoT: terrain, sites and the battery (Step 0 and the battery)

**60 seconds:** "Candidate sites come from NASA LOLA terrain: within 6° of the pole and under 10° of slope over 100 m, NASA's Artemis gates. I made the full grid: 2,436 sites, 5 km apart. The battery model is a Nova-C-class lander:
- 200 W of panels and a 25 Ah, 28 V battery (700 Wh), from published Nova-C figures;
- Nova-C's design life is 14 days, which is our mission length;
- a 50 W load (an estimate from how long Odysseus lasted on battery);
- a 140 Wh reserve (an assumption).

A full battery bridges 11.2 hours of darkness."

- **The limit to admit first:** the model assumes panels that track the Sun, so survival is an upper bound. IM-1 died with tipped, fixed panels while the Sun was still up.

## BIT: the web app

**60 seconds:** "One page, no installation. You choose a lander, a height and a site, and you see the horizon the lander would see, with the Sun and Earth moving hour by hour, the countdowns to sunset and Earthset, the battery, and a verdict in plain English. Then the failsafe card says what happens if things go wrong. The page computes no physics: it shows files our Python pipeline made, so it is instant and works offline from a single file. 'Plan your own mission' runs the real engine on a laptop in about a second."

- **The limit:** "Plan your own mission" needs the local server; everything else works anywhere.

## Business: NASA data, users, impact

**60 seconds:** "Every number comes from NASA data:
- the LOLA terrain and SPICE ephemerides;
- the three Resources-tab tools: JPL Horizons, which checks every Sun and Earth position; Moon Trek, whose 5 m terrain the demo site passes too (and another site fails: finer terrain matters); and Quickmap, one click from every site;
- NASA's own PGDA sunlight maps, which we match with correlation 0.92.

Users: CLPS mission planners choosing a site and a landing window; educators showing why the pole is hard; the public. It runs at zero cost, is open source, and is reproducible from published NASA files with checksums."

- **The limit:** the demo ranks 400 sites in a 9 km square near Shackleton. The same pipeline ran on all 2,436 sites within 6°: 116 of them have a safe landing day at 2 m, and at least 49 stay safe after a 100 m miss. The best, site 422 (87.05°S), keeps 77 safe days at 2 m and 162 at 10 m, and its Earth view matches NASA's map (55.8% vs 54–55%). Details: `docs/region-results.md`.
