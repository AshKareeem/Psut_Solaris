# Use of AI (SI) in LunarWindow

NASA Space Apps permits AI tools but asks teams to say where and how they were used, to acknowledge generated code and data in text and metadata, and to describe how people verified it. This is that statement.

## Where AI was used

| Tool | What it did | When |
|---|---|---|
| **Claude Code** (Anthropic; Claude Opus models) | Wrote most of the Python code at the team's request: the horizon engine, the Sun and Earth step, scoring, battery, validation scripts, the local server and the web build. Also wrote documentation and multi-agent reviews ("LLM council") used to challenge the team's decisions. | Oct 12 – Nov 14, 2026 |
| **Claude Fable 5.2** (Anthropic) | Built the failsafe blocks (`risk`, `contact_plan`, `dark_verdict`, `weak_battery`, `confidence`) overnight, from a written spec, offline, without the NASA data. Its work was reviewed line by line, one bug was fixed, and it was re-run on the real data before merging. | Nov 13–14, 2026 |
| **Claude** (chat) | Helped write the chapter-by-chapter explanation of the horizon engine (`docs/horizon-engine/`). Each chapter was checked against the code. | Oct 2026 |
| **Gemini** (Google) | Made the team's explainer videos from our own documents and figures (linked in the README). They are study material for the team, not part of the product. Any clip shown in the pitch carries a visible AI label. | Oct–Nov 2026 |

The web page's front end was designed by our BIT teammate. AI-assisted fixes were merged during review, Claude Code added the failsafe card overnight on Nov 14 and restyled the page on Nov 14 (type, colours, the real-skyline hero band).

**Not AI-generated:**
- **The data:** every number comes from NASA data (LOLA terrain, SPICE ephemerides, Moon Trek, PGDA) run through our code.
- **The images:** the globe uses NASA's CGI Moon Kit; no image or video in the product is AI-generated.
- **No NASA logos** are used anywhere.

## How we verified it

AI-written code was accepted only when it passed checks people can rerun:

- **152 automated tests** (`python -m pytest tests -q`). Synthetic terrains with known answers (smooth Moon, cone, ring crater), the fast engine against a plain reference engine (to 1e-6°), the direction convention, every Step 3–4 rule, the battery, events to the minute, and real-terrain regressions.
- **Independent checks against NASA:**
  - Sun and Earth positions: 124 checked against JPL Horizons, all within 0.0003°.
  - Sunlight and Earth visibility against NASA's PGDA maps: correlation 0.92 at the Shackleton rim, at a best-fit 2 m height.
  - The demo site on NASA Moon Trek's 5 m terrain.
- **Reviews that found real errors, fixed before the pitch:**
  - The slope gate used a 480 m placeholder instead of NASA's slope over 100 m.
  - Most headline landings were marginal touchdowns.
  - The 100 m check didn't test slope.
  - A bug in the overnight failsafe code.
  
  Each fix is a separate, explained commit.
- **Ownership:** each team member owns a step (see `docs/team-guide.md`) and must be able to explain it line by line. Judges can ask any of us.

## Acknowledgement in the data (metadata)

Every `results.json` (`meta.provenance`) and every mission file (`provenance`) states:

> Computed by the LunarWindow pipeline from NASA LOLA terrain and NASA SPICE (DE421) ephemerides. Code written with AI assistance (Claude Code) and verified by the team with automated tests and a comparison against NASA PGDA illumination maps.

Commits written with AI carry a `Co-Authored-By` line naming the model.

## Timeline

Work before the event is marked by the annotated git tag `pre-event-2026-11-12`. Everything after it was done during the event: `git log --oneline pre-event-2026-11-12..HEAD`.
