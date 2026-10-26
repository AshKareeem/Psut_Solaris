# How our horizon engine works

This is the horizon engine (Step 1) explained chapter by chapter, with the code line by line and exercises to run. It was written with Claude, and each chapter was checked against the code and the real engine output.

| Chapter | File | Status |
|---|---|---|
| 1. The 60-second version | `horizon-01-overview.md` | done, checked |
| 2. The big picture: outputs, files, the pipeline | `horizon-01-overview.md` | done, checked |
| 3. Geometry from first principles | `horizon-02-geometry.md` | done, checked |
| 4. The algorithm, with a real ray | | to come |
| 5. Making it fast | | to come |
| 6–7. Two terrain maps; how we know the settings are enough | | to come |
| 8. Proof it's right | | to come |
| 9. `fast.py` line by line | | to come |
| 10–12. The rest of the code, limitations, judge prep | | to come |

The chapters cite source files by the names they had in the pack they were written from:

| Name in the chapters | File in this repo |
|---|---|
| `02_CLAUDE.md` | Ash's project notes, which aren't in the repo; the numbers they cite are in `README.md` and the team PDF |
| `03_code.md` | the code itself (`horizon/`, `scripts/`, `tests/`) |
| `04_data.json` | real engine numbers at the rim site; regenerate on request |
| `06_README.md` | `README.md` |
| team PDF | `docs/landing-site-algorithm.pdf` |

Line numbers refer to commit `4658698`.
