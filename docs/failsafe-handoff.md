# Failsafe handoff (Fable agent, overnight Nov 13 → 14)

## What was built

All four blocks of `docs/failsafe-spec.md`, in its commit order, tests first, nothing on the Cut list:

1. **`risk`** in every mission file `scripts/score_sites.py` writes: `delay_margin_h`, the 1/6/24/709 h
   `delay_ladder`, the 17-point `miss_table` (first failing rule, slope first), and `words`.
   `neighbour_safe` gained `details=False`; the default 3-value return and both existing callers are unchanged.
2. **`contact_plan`**, **`dark_verdict`**, **`weak_battery`** and their **`words`** in `site_report()`, so both
   `score_sites.py` and `analyze.py` (and `POST /api/mission`) carry them.
3. **`confidence`** in `site_report()`: ±0.02° skyline through the same `events.py`/`battery.py` code.
4. **Data contract** (`docs/ui-data-contract.md`, "Failsafe blocks") with `risk` marked ranked-sites-only,
   one README line under "The web app", and an end-to-end synthetic test (every block present, JSON-round-trips).

Add-fields-only holds: no existing field, `results.json` key, ranking or `battery.step` changed; `web/data/` and
`web/index.html` untouched. Every number is computed by `events.py` / `battery.py` / `date_metrics`, or is one of
the spec's labelled assumptions (0.5× battery, 709 h lunation, 0.02° shift, the battery.py labels).

## Tests

- Baseline on arrival: **136 passed, 6 skipped** (the 6 need `data/`), exactly as expected.
- After commit 4: **143 passed, 6 skipped** (7 new tests, all on synthetic inputs, written before the code).
- Could not run: the 6 data-dependent tests (`test_real_terrain`, `test_analyze_any_coordinates_end_to_end`,
  etc. — no `data/` in the zip, as expected), and no rebuild (`run_profiles.py`/`build_web.py` need `data/` and
  `out/`). Acceptance checks 2b–6 are therefore the reviewer's, per the spec.

## Environment

Python **3.12.3** (not the team's 3.14; 3.11+ as required). `pip install -r requirements.txt` was refused by the
system Python (PEP 668, externally managed) — **no package was missing**, every requirement was already
installed, so nothing failed to import and the suite ran whole. Versions: numpy 2.5.4, numba 0.68.1,
rasterio 1.5.2, pyproj 3.8.0, spiceypy 8.3.0.

## Commits (branch `failsafe`)

| # | Hash | What |
|---|---|---|
| base | `a97de0c` | snapshot of the project as received (see deviation 1) |
| 1 | `0e6475a` | `risk` block in score_sites' mission files |
| 2 | `2f5b6e2` | `contact_plan`, `dark_verdict`, `weak_battery`, `words` in `site_report()` |
| 3 | `e88195b` | `confidence` in `site_report()` |
| 4 | `489da55` | data contract, README line, end-to-end synthetic test |

Nothing reverted. Three of my own tests had wrong hand counts on the first run (709 h counted from hour 0 instead
of the headline hour; `sun_el 0.0` treated as darkness when it is half a disc; an Earth-set crossing at t≈23.7
counted as covering the hour-24 moment); each time the code was right and the test's arithmetic was fixed, with
the corrected count in its comment.

## Deviations and judgement calls

1. **The zip had no `.git` and no `CLAUDE.md`** (and `main` at `3d216f8`/`2095303` was therefore unreachable).
   I initialised a fresh repo, committed the snapshot as `main` (`a97de0c`), and branched `failsafe` from it, so
   `git diff main..failsafe` still reviews exactly my changes. To merge: `git fetch <unzipped folder> failsafe`,
   then **cherry-pick the four commits plus this handoff commit** onto your real `main` (a direct merge would
   drag the unrelated snapshot root in). The zip also contained a byte-identical nested copy of the project
   (`Psut_Solaris-main/Psut_Solaris-main/`), which I removed before the snapshot commit. The code I received
   already contains R1–R3 (option A), matching "2095303 or later".
2. **Ladder label**: the spec's field list is `{slip_h, start_utc, safe, next_safe_utc}` but the 709 h row must
   be "labelled". I added a `label` field on that row only.
3. **`next_safe_utc` on a safe row** is the slipped hour itself ("at or after"), so the test "every non-null
   `next_safe_utc` is a safe hour" holds for all rows.
4. **The ladder uses the same safe series as `delay_margin_h`** (within 100 m when that check ran for the site):
   the spec states the 100 m rule under `delay_margin_h`; I read it as the site's operative safe definition for
   the whole block.
5. **Event stamps carry seconds**, not the contract's "to the minute": `to_utc` inherits the sky file's
   `T00:00:00` precision, and the existing `events.dte` already does this. Followed the code (rule 8);
   `contact_plan` stamps match `events.dte` exactly, which commit 2's test asserts.
6. **`first_contact_utc` may be null** (Earth never in view) — then `missing` lists all three moments and the
   words say no plan can be uploaded. Stated in the contract so check 3's "no null where not allowed" has its
   allowance on record.
7. **`dark_verdict.end` is exclusive** (the first hour after the run), matching the events' half-open flavour;
   stated in the contract.
8. **`words` placement**: the spec's commit-2 schema lists `words` beside the three blocks, so it is a top-level
   key of the mission file (risk's own `words` live inside `risk`).
9. **"before the end of 2030" wording**: when no later safe hour exists, the sentence says "before the data
   ends" rather than hard-coding 2030, so synthetic runs and future spans stay truthful.
10. **Not-lasting sentences** still carry the required phrase, as "even at best (sun-tracking panels)", which is
    the honest direction of the bound.
11. **`confidence` recomputes its own baseline** (δ=0) through the same helpers instead of threading
    `summary` values in; identical code path, so they cannot disagree.

## The `words` my code produces on the synthetic tests

`site_report` words:
- Earth up all mission, a 12 h ridge spell that kills the battery:
  - "Earth in view at touchdown, mid-mission and end: upload the plan at landing and confirm it on 2027-01-01."
  - "1 dark spell, the longest 12 h; the battery does not last through the spell starting 2027-01-01T06 UTC: even at best (sun-tracking panels) it drops below 140 Wh."
  - "With half the battery it dies at hour 11 (2027-01-01T11 UTC), even at best (sun-tracking panels)."
- No darkness, Earth sets before mid-mission:
  - "No Earth contact at mid-mission or end: first contact 2027-01-01T00:00:00 UTC, longest blackout 12 h."
  - "No darkness during the mission."
  - "With half the battery it still survives, at best (sun-tracking panels)."
- 11 dark hours (the full battery survives at 150 Wh, half dies):
  - "Earth in view at touchdown, mid-mission and end: upload the plan at landing and confirm it on 2027-01-01."
  - "1 dark spell, the longest 11 h; the battery lasts through every one, at best (sun-tracking panels)."
  - "With half the battery it dies at hour 5 (2027-01-01T05 UTC), even at best (sun-tracking panels)."

`risk` words:
- Safe hours 3–6 and 30, headline 3, one steep point within 100 m:
  - "Land up to 3 h late and it is still safe; a 6 h slip is not: the next safe hour is 2026-01-02T06 UTC."
  - "Missed by up to 100 m: 1 of 2 points safe; the point 100 m toward bearing 90 deg fails on slope (12.0 deg)."
- Everything safe:
  - "Land up to 799 h late and it is still safe; even one lunation later (709 h) is safe."
  - "Missed by up to 100 m: all 2 points safe."

(On a real 14-day mission the confirm date is mid-mission, +7 days; the 24 h synthetic lands and confirms on the
same date. "Confirm it on …" is only said when all three moments have contact.)

## For the morning review

- The one untested seam is `risk` inside `main()` itself (it needs the real arrays): read the ~15 added lines in
  the detail-file loop first, then rebuild with the Part 2 commands and open `web/data/sites/33_5.0.json`.
- Memory note: `neighbour_safe(details=True)` keeps the per-point metric arrays alive through the write loop
  (the same arrays `date_metrics` always allocated inside it); on the laptop that ran the full grid this is fine,
  but if `run_profiles` ever swaps, this is where.
