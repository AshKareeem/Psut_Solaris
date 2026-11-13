# Build spec: the mission failsafe blocks (backend)

**Who this is for:** the coding agent that builds the backend overnight (Fri Nov 13 → Sat Nov 14, 2026), and the team member who reviews it in the morning. BIT builds the page from `docs/ui-data-contract.md` after this lands.

**Where this comes from:** Ash's four failsafe features, decided by an LLM council (round 10, Nov 13) with five anonymous peer reviews. All five advisors and all five reviewers agreed on the cuts below.

## 0. What to build, and what not to build

**What a judge must believe:** the tool tells the truth about what can go wrong at a landing site, before you commit to it.

| Ash's feature | What gets built | Why |
|---|---|---|
| 1. Sun along a journey + decide: go to sunlight / wait / return | **Only "wait":** for each dark period of the mission, does the battery last until the Sun returns? (`dark_verdict`) | The product models a lander that can't move. No sourced rover speed, drive power, driving slope limit or survival load exists; inventing them fails Validity (the first tie-breaker). "Go" and "return" are future work. |
| 2. Earth contact only at landing, end and 1–2 times en route | **`contact_plan`:** the first contact after touchdown, the windows that cover touchdown, mid-mission and end (when a plan is uploaded and confirmed), and the longest blackout | Same idea, applied to a lander that stays put. All of it comes from the existing Earth-contact events. |
| 3. Slope detector | **Nothing.** It is done: the slope over 100 m on the 20 m map, at all 17 points within 100 m (R3, option A, commit on `main`) | Touching it again tonight adds risk and no evidence. |
| 4. Risk manager: delays, wrong spot, battery drain, calculation errors | **`risk`** (delays, wrong spot), **`weak_battery`**, **`confidence`** (calculation errors and what the tool can't see) | The machinery exists; what's missing is a view of it. |

**Cut, for one future-work line on a slide:**
- the rover decision tree (branches "go" and "return");
- journeys and routes;
- "nearest sunlit ground";
- any new physics;
- re-running `scripts/sensitivity.py` (its output is stale);
- any refactoring.

The future-work line: *"Per-point skyline + SPICE sky is the core of a traverse planner once a drive model exists."*

## 1. Rules (Ash's; break none)

- **Work on a branch** named `failsafe`, made from `main` after the R3 commit. Push the branch. **Never merge into `main`**: Ash merges after the morning checks.
- **Add fields only.** No existing field, file name, `results.json` key, ranking, or `battery.step` changes. A `git diff` of `web/data` after the rebuild must show only additions.
- **No new physics, and no new formula for an existing quantity:**
  - Sun and Earth visibility come from `scripts/events.py`.
  - The battery comes from `scripts/battery.py` (`step`, `levels`, `simulate`).
  - The multi-year landing flags come from `score_sites.date_metrics`.
- **Every number** is either computed by existing code or a labelled assumption with its reason. The assumptions in this spec:
  - the 140 Wh reserve and 50 W load (already labelled in `battery.py`);
  - the 0.5× battery case;
  - the one-lunation slip (29.53 days = 709 h);
  - the ±0.02° skyline shift (it comes from the convergence study);
  - the sun-tracking upper bound.
- **Every "survives" or "lasts" sentence** says *"at best (sun-tracking panels)"*. Real landers have fixed panels; IM-1 died tipped with fixed panels while the Sun was still up.
- **Fail fast** with a clear error; no fallbacks; simple code; one function per job; a test for every rule.
- **Never commit** `CLAUDE.md` or `Council opinion.md` (both are gitignored; keep it that way). Never rewrite history. End each commit message with the line `Co-Authored-By: <your model name> <noreply@anthropic.com>`.
- **Stop by 05:00 local.** If a block's tests fail and a fix isn't obvious, revert that commit and say so in the handoff; don't leave a broken block.

## 2. Where the data lives (read this before coding)

- **`scripts/site_report.py` `site_report(site, H, D, complete, track, mast, battery, earth_margin)`** builds one mission file. It sees **one mission**: its hourly track, the skyline at one mast, and the battery. Both `scripts/score_sites.py` (ranked sites) and `scripts/analyze.py` (any coordinates, used by `serve.py` POST `/api/mission`) call it. **A block added here appears in both.**
- **`scripts/score_sites.py` `main()`** holds the multi-year arrays:
  - `met` from `date_metrics`: `safe`, `touchdown`, `n_earth`, `death_h`, `lowest_Wh`, each [sites, masts, landing hours 2026–2030];
  - `firm` (firm touchdown);
  - `head` (the headline landing index per site and mast);
  - with `--neighbours`, the 17 points: `nb` (`sites.csv` with `parent` and **each point's own slope**) and `safe_100m`.
  
  It writes `sites/<id>_<mast>.json` in the loop at the end of `main()`. **A block that needs years of hours or the 17 points is built there and added to the report dict before it is written.**
- The rebuild:
  - `python scripts/run_profiles.py --horizon out/pipe/horizon --sky out/pipe6/sky.npz --sites out/sites/sites.csv --coarse data/ldem_75s_240m.lbl --fine data/ldem_80s_20m.lbl --out out/profiles_failsafe` (about 15 minutes);
  - then `python scripts/build_web.py --profiles out/profiles_failsafe`;
  - both need `data/` and `out/` on Ash's laptop.

## 3. The blocks, in commit order

### Commit 1: `risk`, in `score_sites.py main()` (ranked sites' mission files only)

Add `report["risk"]` to every mission file `score_sites.py` writes:

```
risk
  delay_margin_h      consecutive safe landing hours starting at the headline hour, counted from met["safe"]
                      (within 100 m: safe_100m when the check ran for this site, else met["safe"]); 1 = only the
                      headline hour itself is safe
  delay_ladder [{slip_h, start_utc, safe, next_safe_utc}, ...]   slips of 1, 6, 24 and 709 h (709 = one lunation,
                      labelled "one lunation (29.53 days)"); next_safe_utc = the first safe hour at or after the
                      slipped hour (null if none before the end of 2030)
  miss_table [{point, dx_m, dy_m, safe, fails}, ...]    the 17 points at the headline hour (null for unchecked sites);
                      fails = the first rule that fails, in this order: "slope" (point slope >= 10 deg),
                      "sun at touchdown" (s <= 0.5), "earth at touchdown", "earth for the mission"
                      (n_earth < min_dte_share x hours), "battery" (death_h >= 0); null when safe
  words [sentence, ...]   plain English, e.g. "Land up to 7 h late and it is still safe; a 24 h slip is not: the
                      next safe hour is 2028-09-03T02 UTC." and "Missed by up to 100 m: 15 of 17 points safe; the
                      point 100 m toward bearing 40 deg fails on slope (11.7 deg)."
```

- `miss_table` needs each point's metrics at the headline hour. `neighbour_safe` currently returns only the combined `safe`, so add the smallest change that also returns the per-point `date_metrics` and visibility it already computes. Keep its existing return values and callers working.
- Bearings in `words` use `site_report.bearing(theta, lon)`. A point's offset direction θ is `atan2(dy, dx)` in degrees.
- `analyze()` files have **no** `risk` block, because `analyze` has no multi-year array. Write that into the data contract as a documented scope, not a fallback.
- **Tests** (`tests/test_score_sites.py`):
  1. `delay_margin_h` on a tiny synthetic safe array, counted by hand in the test's comment.
  2. Every non-null `next_safe_utc` in the ladder is a safe hour.
  3. On a synthetic two-point case, the miss table's `safe` flags agree with `safe_100m` at that hour, and a steep point reports `"slope"` first.

### Commit 2: `contact_plan`, `dark_verdict`, `weak_battery`, in `site_report()`

```
contact_plan
  first_contact_utc       start of the first Earth-contact window at or after touchdown ("YYYY-MM-DDTHH:MM")
  windows [{start, end, covers}, ...]   the contact windows (events.dte) that contain touchdown, the mission's
                          middle hour and its last hour; covers = subset of ["touchdown", "mid-mission", "end"];
                          a moment with no window is listed in missing
  missing [name, ...]     which of touchdown / mid-mission / end has no Earth contact
  longest_blackout_h      = summary.longest_earth_blackout_h
dark_verdict [{start, end, hours, battery_start_Wh, battery_lowest_Wh, lasts}, ...]
                          every run of hours with s <= 0.5 (Sun under half visible), from the battery level series
                          levels(s, battery); lasts = the level never drops below e_min in that run; [] when the
                          Sun never sets
weak_battery              {capacity_factor 0.5, e_max_Wh, e_min_Wh, survives, dies_at_hour, label}: the same mission
                          through battery.simulate with Battery(e_max x 0.5, e_min x 0.5, same panel and load): the
                          reserve stays 20% of a full battery, as battery.py defines it; label "assumption: half the
                          battery, e.g. a cell lost or a cold battery"
words [sentence, ...]     e.g. "Earth in view at touchdown, mid-mission and end: upload the plan at landing and
                          confirm it on 2028-09-09." "No darkness during the mission." "With half the battery it
                          still survives, at best (sun-tracking panels)."
```

- **Tests** (`tests/test_site_report.py`, reusing its `track()` helper):
  1. Every `contact_plan.windows` entry is an exact entry of `events.dte`.
  2. `missing` names a moment with no Earth.
  3. `dark_verdict` agrees with `summary`: some run has `lasts` false exactly when `summary.survives` is false, and the longest run equals `longest_dark_h`.
  4. `weak_battery` at factor 1.0 (call the helper with 1.0 in the test) reproduces `summary.survives` and `summary.dies_at_hour`.

### Commit 3: `confidence`, in `site_report()`

```
confidence
  skyline_shift_deg 0.02                  the convergence study's bound: every site within 0.02 deg in 99% of
                                          its directions
  sunset_shift_min, earthset_shift_min    how many minutes the first sunset and first Earthset after touchdown
                                          move when the whole skyline is raised and lowered by 0.02 deg (the
                                          larger of the two); null if that event doesn't happen in the mission
  verdict_changes                         true if raising or lowering the skyline by 0.02 deg flips
                                          summary.safe_landing
  checks [sentence, ...]                  static, with their numbers: "Sun and Earth positions: 124 checked
                                          against NASA JPL Horizons, all within 0.0003 deg." "Sunlight: matches
                                          NASA's PGDA map at the Shackleton rim, correlation 0.92 (2 m best fit)."
  cannot_see [sentence, ...]              static: "Hazards smaller than the 20 m map, like the ~20 m crater IM-2
                                          tipped into." "A tilted lander with fixed panels, like IM-1: survival
                                          here is an upper bound."
```

- The shifted runs **call the same `events.py` functions** with `H ± 0.02`. No copy of the event logic.
- **Tests:** a 0.0° shift gives 0 minutes and `verdict_changes` false; on a synthetic track whose Sun crosses the skyline at a known rate, a 0.02° shift moves sunset by the expected minutes (worked out in the test's comment).

### Commit 4: data contract, README line, rebuild

- **`docs/ui-data-contract.md`:** add every new block and field, its source, and its labels, under the mission-file schema. Mark `risk` as "ranked sites only". This is the frozen schema BIT builds from in the morning.
- **README:** one line under "The web app", naming the failsafe blocks.
- **The data:**
  - Rebuild with the two commands in Part 2.
  - Commit `web/data` on the branch.
  - Check that `git diff --stat main -- web/data` shows only modified or added site files and that `results.json` is byte-identical except where the R3 commit already changed it. Compare with `git diff main -- web/data/results.json`; it should be empty, since `risk` lives in the site files.

## 4. Morning acceptance checks (Ash, about 10 minutes)

1. `python -m pytest tests -q`: green, with 142 plus the new tests.
2. `git log --oneline main..failsafe`: four separate commits.
3. `web/data/sites/33_5.0.json` has `risk`, `contact_plan`, `dark_verdict`, `weak_battery` and `confidence`, with no null where this spec doesn't allow one and no unlabelled constant.
4. `python scripts/serve.py`, then plan a mission at site 33 in the page. The answer carries `contact_plan`, `dark_verdict`, `weak_battery` and `confidence`.
5. `git diff main..failsafe -- web/data/results.json` is empty.
6. **The stranger test:** someone outside the team reads site 33's `words` sentences cold. In under 30 seconds they can say whether to land there, when, and what the fallback is.
7. All six pass → merge `failsafe` into `main` and push. Any one fails → merge only the commits that pass, or none.

## 5. Handoff note

When done, write `docs/failsafe-handoff.md` with:
- what was built;
- the test count;
- the four commit hashes;
- anything reverted, and why;
- site 33 at 5 m's `words` sentences pasted in, so Ash can run the stranger test from his phone.
