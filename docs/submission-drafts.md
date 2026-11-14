# Submission drafts (for Ash and Business to edit, then paste or send)

Drafted by Claude on Sat Nov 14, 03:00–05:00. **Nothing here has been sent or submitted.** Every number traces to a file in the repo; the source is in brackets. Fill in the `[NAMES]` placeholders yourselves.

---

## 1. Project name

**LunarWindow**: when and where a lander at the Moon's south pole gets sunlight and Earth.

## 2. High-Level Summary (50–200 words; this draft is 167)

LunarWindow tells mission planners, educators and the public whether a solar-powered lander at the Moon's south pole will have sunlight and a direct link to Earth when it lands, whether it survives its mission, and why. From NASA's LOLA laser-altimeter terrain, we compute each candidate site's real horizon in 1,440 directions out to 250 km. NASA's SPICE toolkit gives the Sun and Earth every hour from 2026 to 2030. Every possible landing hour is tested against NASA's Artemis III rules: within 6° of the pole, slopes under 10°, contact with Earth without a relay, and safety if the lander misses its target by up to 100 m. Sites are ranked by how many safe landing days they offer, never by a weighted score, and every rank explains itself in plain words. A failsafe card shows what a delay, a missed target or a weaker battery would do. Our Sun and Earth positions match NASA JPL Horizons to 0.0003°, and our sunlight matches NASA's own maps (correlation 0.92).

## 3. Demo link

The one link: the 7-slide deck (Business). The outline is in section 7.

## 4. Final Project link

https://github.com/AshKareeem/Psut_Solaris. Once GitHub Pages is on, add the page link too (section 9, step 3).

## 5. Project Details

**What it does.** Pick a landing site near the south pole, a landing hour and a lander. LunarWindow shows:
- the horizon the lander would see, with the Sun and Earth moving across it hour by hour;
- when the panels charge and when Earth is in view, to the minute;
- the countdown to sunset and Earthset;
- the battery through the mission;
- a verdict with the reason: which hill, how far away, in which direction.

It has been run on all 2,436 candidate sites within 6° of the pole (116 have a safe landing day at 2 m). It ranks every candidate site by its number of safe landing days: power and Earth at touchdown, Earth in view for at least half the mission, and a battery that never drops below its reserve. A lander can come down anywhere within 100 m of its target, so a date only counts if it is safe at 17 points within 100 m, each on ground under 10°. A failsafe card answers "what if":
- the landing slips by an hour, a day or a lunar month;
- the lander misses by 100 m;
- the battery holds half its charge;
- the horizon is 0.02° off.

**How it works.**
1. A ray-traced horizon engine walks great circles over NASA LOLA terrain: 20 m pixels near the site, 240 m out to 250 km, including the Moon's curvature, in about 3.5 ms per site.
2. NASA SPICE (DE421) gives the Sun and Earth for every site and hour.
3. A battery model runs the mission from every possible landing hour.
4. Results are precomputed into files, so the web page answers instantly and computes no physics.
5. A local server runs any custom coordinates through the same engine in 1–3 seconds.

**How we know it is right.**
- **152 automated tests**, including terrains with known answers.
- **The settings were chosen by a convergence study:** every site's skyline is within 0.02° of the finest settings in 99% of its directions.
- **NASA JPL Horizons:** 124 Sun and Earth positions, all within 0.0003°, and every mission links Horizons' own table for that site and hour, so anyone can check.
- **NASA's PGDA sunlight maps:** correlation 0.92 at 100 pixels around Shackleton (2 m best-fit height).
- **NASA Moon Trek's 5 m terrain:** the demo site passes on it too, and another site that passes on our 20 m map fails on it, which showed us where finer terrain changes the answer.
- **Our limits are stated in the product:** the battery assumes sun-tracking panels, so survival is an upper bound.

**Benefits.**
- **Planners** get landing windows with margins, not a single average.
- **Educators** get a visual explanation of why the pole is hard.
- **The public** gets plain-English verdicts.
- It runs on a laptop at zero cost and is open source (MIT).

**Goals.**
- Make south-pole lighting and Earth contact understandable in seconds.
- Show that a landing site is a point in time, not just a point on a map.

**Tools and languages.** Python (NumPy, Numba, rasterio, pyproj, SpiceyPy, Skyfield, pandas, matplotlib, Pillow, pytest); HTML/JavaScript (one page, no framework).

## 6. Use of SI (AI)

**Dropdown:** yes (AI used).

**Text (paste):**

> Code was written with AI assistance: Claude Code (Anthropic) for most of the pipeline and web build, and Claude Fable 5.2 for the failsafe blocks, built from a written spec and reviewed line by line. The team verified it with 152 automated tests and independent checks against NASA JPL Horizons, NASA PGDA maps and NASA Moon Trek terrain. Every data file states AI assistance in its metadata, and AI-written commits are marked. Gemini made explainer videos for the team's own study. No image or video in the product is AI-generated, and no NASA logos are used. Details: AI_USE.md in the repository.

## 7. Deck outline (7 slides; the title counts) and its numbers

| # | Slide | The number on it | Source |
|---|---|---|---|
| 1 | **Title:** LunarWindow, team Psut_Solaris, `[NAMES]`, the challenge name; one screenshot of the mission player | — | — |
| 2 | **Problem:** south-pole landers live or die by a Sun and Earth just above the horizon. IM-1 tipped over and lasted about a week; IM-2 landed on its side in shadow and ended in under 13 hours. | Sun within ±1.5° of the horizon | `docs/team-guide.md` Part 3.1 |
| 3 | **What a user does:** pick lander → height → site → landing hour; see the horizon, Sun and Earth, countdowns, verdict and why | demo: site 210 at 10 m, landing 2026-01-21 07:00 UTC; Sun 2.98° and Earth 0.56° above the skyline | `web/data/sites/210_10.0.json` |
| 4 | **How it works + NASA data:** LOLA → horizon (1,440 directions, 250 km); SPICE → Sun and Earth; battery → survival; 100 m and slope checks. Resources tab: Horizons, Moon Trek, Quickmap | ~3.5 ms per site | team guide 4.2 |
| 5 | **Evidence (Validity):** Horizons, PGDA, Moon Trek, tests, convergence | 0.0003° · r = 0.92 · 152 tests · 0.02° | README Parts 7–9 |
| 6 | **Findings:** a landing site is a point in time. The rim site is dark at 2 m and the best site at 10 m. No 2 m site survives a 100 m miss. Site 33 passes on our 20 m map but fails on NASA's 5 m map: finer terrain changes the answer (the IM-2 lesson). | 0.3% vs 85.9% (rim vs crest 103 m away) · 337 safe days, 315 within 100 m (site 210 at 10 m) · **the whole region: 2,436 sites within 6°, 116 with a safe day at 2 m, at least 49 safe after a 100 m miss** | `tests/test_real_terrain.py`, `web/data/results.json`, `docs/region-results.md` |
| 7 | **Timeline, AI use, sustainability, next:** before and during the event (tag `pre-event-2026-11-12`); AI verified by tests and NASA checks; zero running cost. Next: fixed-panel geometry, newer 5 m terrain across the region, traverse planning once a rover model exists. | 45 event commits | `git log pre-event-2026-11-12..` |

**Labels the deck must carry:** "400-site demo grid near Shackleton" on slides 3 and 6. "Survival is an upper bound (sun-tracking panels)" wherever survival is shown.

## 8. Organizer disclosure (Ash sends, in writing, before the judging slot)

> Hello, we are team Psut_Solaris (Lunar Landing Site Navigator). We want to disclose prior work and ask how you'd like it presented. Between Oct 12 and Nov 12 we built and validated a terrain-horizon engine on NASA LOLA terrain and NASA SPICE ephemerides, checked against NASA PGDA illumination maps. It has been public on GitHub (MIT) since Oct 26, now at github.com/AshKareeem/Psut_Solaris. The state before the event is marked by the annotated git tag `pre-event-2026-11-12`; everything after it was done during the event (`git log pre-event-2026-11-12..HEAD`). During the event we built:
> - landing at any hour;
> - the battery and ranking fixes;
> - lander presets;
> - checks against JPL Horizons and NASA Moon Trek;
> - the slope-within-100 m rule;
> - the failsafe card;
> - the web interface on real data.
>
> The code was written with AI assistance, which our AI-use statement describes. Is this eligible, and how would you like us to present the split between prior and event work? Thank you.

## 9. Human-only steps (Claude cannot do these)

1. **Send the disclosure** (section 8), in writing, before the judging slot.
2. **Team names:**
   - put all six on slide 1 and on the submission page;
   - add them to the README under "Team" (`[NAMES]`);
   - check that all six are registered for Amman & Aqaba and none is waitlisted.
3. **GitHub Pages:**
   - repo **Settings → Pages → Deploy from a branch → `main` / root**. The page then lives at `https://ashkareeem.github.io/Psut_Solaris/web/`.
   - Open it in a private window to check.
   - Without the local server, "Plan your own mission" is labelled as local-only; everything else works.
4. **Click "Submit for Judging"** after the pitch; it can be resubmitted until Sun 23:59.
