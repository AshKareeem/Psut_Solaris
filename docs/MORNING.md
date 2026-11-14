# Morning, Sat Nov 14: read this first (2 minutes)

Written by Claude overnight (Nov 14, 03:00–05:00), following LLM council round 11. **The backend is finished: this morning is frontend only.**

## ⚠ Before anything else (human only)

1. **Send the organizer disclosure** (text ready in `docs/submission-drafts.md` §8), in writing, **before the judging slot**. It is the only item that can disqualify us whatever the quality. The evidence is the tag `pre-event-2026-11-12`.
2. **The demo changed to site 210 at 10 m** (the Shackleton rim site). Reason below. Rehearse with it.

## Done overnight (on `main`, pushed)

- **Fable's failsafe blocks reviewed line by line, one bug fixed, merged.**
  - **The blocks:** `risk`, `contact_plan`, `dark_verdict`, `weak_battery`, `words`, `confidence`.
  - **The bug:** sites with no date safe within 100 m (every 2 m site) had their delays counted on the wrong series, so they reported "0 safe hours". `risk.basis` now says which rule was used.
  - **The wording:** failed points read as plain English.
- **`web/data` rebuilt** with all the blocks for every preset. `results.json` is byte-identical: rankings and numbers are unchanged.
- **The demo site re-checked on NASA Moon Trek's 5 m terrain.**
  - **Site 33 at 5 m fails there** (a 7–8 m rise 20 m away, which the 20 m map doesn't show). The maps disagree by a median of 4.2 m near the pole.
  - **Site 210 at 10 m passes on both maps:** 337 safe days, 315 within 100 m, all 17 points under 6.4°. So it is the demo.
  - Site 33 stays as the honest example: finer terrain can change the answer.
- **Required AI-use statement:** `AI_USE.md`, plus a line in the README; every data file states it in its metadata. (The page footer line was removed by the team on Nov 14.)
- **Stale claims fixed:**
  - the page's "140 tests" is now 152;
  - the Moon Trek trust card now names site 210 and site 33;
  - the README's test counts and the 13 MB standalone size.
- **Reproducibility:**
  - `requirements.txt` is pinned to the versions the tests pass with;
  - the README has a **Data** section with every NASA file, its source and its SHA-256.
- **Drafts for the submission page** (`docs/submission-drafts.md`):
  - name;
  - the 167-word summary;
  - Project Details;
  - the Use of SI text;
  - a 7-slide outline with each slide's number and its source;
  - the disclosure.
- **Team guide** (`docs/team-guide.md`) updated: the new demo, the failsafe card, the Moon Trek finding, the judge questions.
- **Tests:** 152 pass (146 + 6 skipped without `data/`).
- **The whole region** (`docs/region-results.md`): all 2,436 candidate sites within 6° of the pole ran through the full pipeline.
  - **116 sites** have a safe landing day at 2 m; **at least 49** stay safe after a 100 m miss.
  - **The best, site 422** (87.05°S, 24.19°W), keeps 77 safe days at 2 m and 162 at 10 m, and its Earth view matches NASA PGDA (55.8% vs 54–55%).
  - The demo stays at the Shackleton rim (site 210), which the page shows; the region goes on slide 6.
- **The algorithm PDF is recompiled** (8 pages, Steps 4–5 current), and **`docs/pitch-cards.md`** gives each member a 60-second card and the 7-minute script.

## For BIT (frontend, this morning)

1. `git pull` first. Overnight edits touched only 4 lines of `web/index.html`: two test counters (now 152), the Moon Trek trust card, and the AI line in the footer.
2. **The demo path to build around:** Your lander → **10 m** → Best sites → **site 210** → Play the mission → the failsafe card.
3. **Already built overnight (commit `749ea06`); polish it if you like, don't rebuild it:**
   - **the failsafe card** under the mission player: late landing, the 17-point ring, the Earth plan, dark spells, half battery, how sure we are;
   - **the steepest ground within 100 m** in the site line;
   - **a "What these words mean" glossary;**
   - **a direct demo link,** `index.html#site=210&mast=10`, for the deck or a QR code.
4. **"The region" tab** (BIT's v16 tabs: Planner / The region / Your mission / Learn): at the selected height, how many of the 2,436 sites have a safe day, and the best 8 with Quickmap links (`web/data/region.json`).
5. **Backup recording of the demo path:** `docs/media/lunarwindow_demo_site210_10m.gif`. It carries an AI tool watermark.

## Stale outside the repo (fix or don't use)

| Where | Old | Now |
|---|---|---|
| `Team_Work/LunarWindow_runs_summary_v2.xlsx` | demo 190 at 2 m; 79 / 18 days | demo **210 at 10 m: 337 / 315 days**; no 2 m site survives a 100 m miss |
| any slide or notes | "190 is #1 at 2 m"; "site 33 is the demo" | 210 is #1 at 10 m; 33 is #1 at 5 m but fails on Moon Trek 5 m |

## Still human-only

- **Names:** the six names on slide 1, the submission page and the README; check all six are registered (not waitlisted).
- **GitHub Pages: done.** Live at https://ashkareeem.github.io/Psut_Solaris/
- **The deck (Business):** from the outline in `docs/submission-drafts.md` §7, numbers as given there.
- **Submit:** "Submit for Judging" after the pitch; resubmitting is allowed until Sun 23:59.
