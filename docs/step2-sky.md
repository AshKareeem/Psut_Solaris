# CE 2: Sun and Earth positions (Step 2)

Part of LunarWindow, our Lunar Landing Site Navigator (NASA Space Apps 2026, team Psut_Solaris).
This step computes where the Sun and Earth are in each landing site's sky, every hour, using NASA's SPICE
toolkit. CE 3 compares these positions with Ash's skylines (Step 1) to find when each site has sunlight and
Earth contact.

**Status: done and validated.** Fully tested against Ash's engine, an independent astronomy library, known
Moon physics, and bad inputs. See the validation report below.

## Files

| File | What it is |
| --- | --- |
| `scripts/make_sky.py` | The Step 2 script. Makes `sky.npz`. |
| `scripts/validate_sky_skyfield.py` | Independent check of `sky.npz` with the Skyfield library. |
| `tests/test_sky_joint.py` | Joint test with the horizon engine (50 cases), part of `python -m pytest -q`. |
| `docs/step2-sky.md` | This document. |

The packages (`spiceypy`, `pandas`, `skyfield`) are in `requirements.txt`.

## Where CE 2 sits in the pipeline

```
IoT ──sites.csv──► Step 1: skylines ──horizon.npy──► Steps 3–4 (scripts/score_sites.py) ──results.json──► web app
 │                                                    ▲
 └──sites.csv──► Step 2: Sun and Earth ──sky.npz──────┘
```

Step 2 needs only `sites.csv`. It does not need terrain maps or the engine's output.

## Run

```
python scripts/make_sky.py --sites sites.csv --year 2027 --out sky.npz
python scripts/validate_sky_skyfield.py --sky sky.npz --heights sites.csv
```

Wait for `ALL CHECKS PASSED` and `SKYFIELD CHECK PASSED`. The first run downloads about 19 MB of NASA SPICE files
into `data/kernels/`; later runs reuse them. In Colab, clone the repo, `pip install -r requirements.txt`, and run
the same commands with `!` in front.

## Commands

| Goal | Command |
| --- | --- |
| Main run: all of 2027, hourly | `python scripts/make_sky.py --sites sites.csv --year 2027 --out sky.npz` |
| Another year | `python scripts/make_sky.py --sites sites.csv --year 2028 --out sky_2028.npz` |
| Custom span | `python scripts/make_sky.py --sites sites.csv --start 2027-03-01 --days 30 --out sky_march.npz` |
| NASA map comparison (18.6 years, every 6 h) | `python scripts/make_sky.py --sites pgda_sites.csv --start 2007-01-01 --days 6794 --step 6 --out sky_pgda.npz` |
| Independent check | `python scripts/validate_sky_skyfield.py --sky sky.npz --heights sites.csv` |
| Joint test with the engine | `python -m pytest -q tests/test_sky_joint.py` |

### Options

| Option | Default | Meaning |
| --- | --- | --- |
| `--sites` | required | sites.csv (needs `id`, `lat`, `lon`; uses `height` in metres if present) |
| `--year` | 2027 | A whole calendar year, hourly |
| `--start` | — | Start date `YYYY-MM-DD`; overrides `--year` |
| `--days` | — | Length in days; required with `--start` |
| `--step` | 1 | Hours between samples |
| `--kernels` | `data/kernels` | Folder for the NASA SPICE files |
| `--out` | `sky.npz` | Output file |

Dates must be between 1900-01-02 and 2049-12-30 (the coverage of the NASA files).

## Input: sites.csv

Ash's format from `horizon/sites.py`: `id, x, y, lat, lon, height, slope`. CE 2 uses:

| Column | Meaning |
| --- | --- |
| `id` | Unique site id |
| `lat` | Latitude, degrees (negative, south) |
| `lon` | Longitude, degrees east (−180..180 or 0..360 both work) |
| `height` | Metres above the 1,737.4 km sphere (0 if the column is missing) |

The script stops with a clear message on duplicate ids, missing columns, empty or non-number values, northern
latitudes, or heights over 20 km. It warns (but continues) for sites more than 6° from the pole.

## Output: sky.npz

| Key | Shape | Meaning |
| --- | --- | --- |
| `site_id` | [sites] | Ids from sites.csv, same order |
| `site_lat`, `site_lon` | [sites] | Degrees, so CE 3 can check the order |
| `time_utc` | [hours] | `YYYY-MM-DDTHH:00:00`, UTC |
| `sun_az`, `earth_az` | [sites, hours] float32 | Direction θ in degrees, team convention, always 0 ≤ θ < 360 |
| `sun_el`, `earth_el` | [sites, hours] float32 | Height above the level horizon, degrees |
| `sun_radius_deg`, `earth_radius_deg` | [hours] float32 | Apparent disc radius seen from the Moon (Sun 0.269–0.272°, Earth 0.898–1.022°) |
| `source` | — | `"SPICE"` (CE 3 sets `sky_source` from this) |
| `step_hours` | — | Hours between samples |
| `frame`, `kernels`, `convention`, `script_version` | — | Record of how the file was made |

Positions are the apparent centres of the Sun and Earth. Steps 3–4 use the per-hour radii above in the
visibility formulas (Earth's changes by 0.12° over a month, which shifts rise and set times by up to about an hour).

```python
import numpy as np
sky = np.load("sky.npz")
sky["sun_el"].shape        # (sites, hours)
str(sky["source"])         # 'SPICE'
```

**Still to confirm with CE 3:** that its notebook reads these key names. If not, rename the keys; the
numbers don't change.

## The direction convention

From the team plan (`docs/landing-site-algorithm.pdf`) and Ash's engine (`horizon/dem.py`):

- θ is measured from the map's +x axis, counterclockwise, 0–360°.
- Longitude 0 is map up (θ = 90°), so Earth always sits near θ = 90°. Longitude 90°E is map right (θ = 0°).
- Map: south polar stereographic, `+proj=stere +lat_0=-90 +lon_0=0 +R=1737400`.

SPICE-style azimuth A is clockwise from local north. The conversion (study guide section 3.10) is:

```
θ = β − A,   β = 90° − lon
```

β is the direction of local north on the map. Ash's study guide computes it numerically by projecting a point
just north of the site. On this map every meridian is a straight line from the pole, and the map at longitude λ
points along (sin λ, cos λ), so local north is at angle 90° − λ exactly. The two methods give the same answer.

## How it works

1. **NASA SPICE files** (downloaded on the first run, checked for broken downloads):

   | File | Contents |
   | --- | --- |
   | `naif0012.tls` | Leap seconds (UTC to SPICE time) |
   | `de421.bsp` | Positions of the Sun, Earth and Moon, 1900–2050 |
   | `moon_pa_de421_1900-2050.bpc` | The Moon's exact orientation over time (its wobble) |
   | `moon_080317.tf` | Defines the Moon's body frames |

2. **Frame:** `MOON_ME_DE421`, the Moon's Mean Earth / polar axis frame. LOLA's terrain maps, and so Ash's
   skylines, use this exact frame. The team plan suggests DE440 as an example; DE421 is used because it is
   the version LOLA's maps are built on, so terrain and sky line up exactly.
3. **Each hour:** the apparent Sun and Earth seen from the Moon's centre (`spkpos` with light time and
   aberration, `LT+S`).
4. **Each site:** place it on the 1,737.4 km sphere plus its height, take the vector to the Sun or Earth, and
   measure it against the site's local up, east and north.
5. **Height:** the angle above the level plane perpendicular to the Moon's radius. Ash's engine
   (`horizon/reference.py`) measures the skyline from exactly this level, so the two compare directly.
6. **Direction:** azimuth A clockwise from north, converted to θ.

## Built-in checks (every run)

| Check | What it tests | Pass rule |
| --- | --- | --- |
| 0 | Direction convention (Ash's test cases, sites near and at the pole) | Error under 0.01°; stops the script if it fails |
| 1 | No missing values; directions in 0–360 | All values valid |
| 2 | Sun height | Never above the site's distance from the pole + the Moon's 1.54° tilt (+ margin) |
| 3 | Earth direction | Each site's median within 15° of θ = 90° |
| 4 | Earth height | Within distance from pole + 7.5° (libration about 6.7°) |
| 5 | Sun circles the sky | Turns over the run = days ÷ 29.53, within 1 |

The script ends with `ALL CHECKS PASSED` (exit code 0) or `SOME CHECKS FAILED` (exit code 1). Don't send a
failed file to CE 3.

## Validation report (November 8, 2026)

Every test was run with the real NASA SPICE files, not fake positions.

### 1. Matches Ash's engine (joint test, study guide 3.10)

`tests/test_sky_joint.py` places a cone near a site, lets Ash's engine compute the skyline, and lets CE 2
compute the direction and height of the cone's tip. 5 sites (from the pole out to 5.8°) × 5 directions × 2
mast heights = 50 cases.

| Measure | Worst difference | Limit |
| --- | --- | --- |
| Direction | 0.005° | 0.05° |
| Height | 0.03° (from the engine's 20 m terrain sampling) | 0.05° |
| Fake Sun 0.5° behind the cone | hidden in every case | hidden |
| Fake Sun 0.5° above the cone | fully visible in every case | visible |

Result: **50 passed**, also against the great-circle engine (Nov 11). The whole suite: **88 passed** with the
LOLA maps in `data/`.

### 2. Matches an independent library (Skyfield)

Same NASA data, completely separate code for frames, light time, aberration and local directions.

| Run | Sites × hours compared | Worst difference (Sun dir / Sun height / Earth dir / Earth height) |
| --- | --- | --- |
| 400-site demo grid around Shackleton | 8 × 300 | 0.00002° / 0.00000° / 0.00000° / 0.00003° |
| 2,436 sites within 6° (IoT scale) | 10 × 300 | 0.00002° / 0.00000° / 0.00000° / 0.00003° |
| Edge cases (exact pole, 5.8° out, lon 0–360) | 6 × 300 | 0.00002° / 0.00000° / 0.00000° / 0.00021°* |
| 18.6-year run, 6 h steps | 8 × 300 | 0.00002° / 0.00000° / 0.00000° / 0.00032°* |

\* Heights not passed to Skyfield for these runs; a few hundred metres of height moves Earth by < 0.001°.

### 3. Matches known Moon physics

| Fact | Expected | CE 2 result |
| --- | --- | --- |
| Sun height at the pole | ±1.54° (the Moon's tilt) | −1.548° to +1.552° |
| Earth height at the pole | about ±6.7° (libration) plus up to 0.26° parallax | −7.10° to +6.57° |
| Earth bobbing period | 27.21 days (draconic month) | 27.18 days |
| Sun turns per year | 365 ÷ 29.53 = 12.36 | 12.36 |
| Sun turns over 18.6 years | 230.07 | 230.06 |
| Earth direction | near θ = 90° | median within 0.3° at every site |
| UTC to SPICE time in 2027 | 32.184 s + 37 leap seconds = 69.184 s | 69.184 s |
| `MOON_ME` vs LOLA's DE421 frame | identical | identical (rotation = identity) |

### 4. Edge cases and bad inputs

| Case | Result |
| --- | --- |
| Site exactly at the pole, lon 0 vs lon 77 | identical output |
| lon −100 vs lon 260 | identical output |
| Duplicate ids / empty lat / northern latitude / missing column / dates after 2049 | stops with a clear message |
| Short run (30 days, 3 h steps) | runs; the Sun-circling check is skipped with a note |
| v3 output vs v2 output | identical (difference 0.0) |

### 5. Speed and size

| Run | Time | File size |
| --- | --- | --- |
| 400 sites, 2027 hourly | about 3 s | 49 MB |
| 2,436 sites, 2027 hourly | about 17 s | 288 MB |
| 100 sites, 18.6 years at 6 h | about 3 s | 37 MB |

## Changes

| Version | Change |
| --- | --- |
| v4 (repo) | Moved into the repo (`scripts/make_sky.py`); `de421.bsp` link fixed (NAIF moved it to `a_old_versions/`); `sun_radius_deg` and `earth_radius_deg` added; kernels in `data/kernels/` |
| v3 | Frame named exactly `MOON_ME_DE421`; stronger input checks; broken-download detection; date range check; Sun-circling check automated; `site_lat`, `site_lon`, `script_version` added to the output; exit code 1 on failure; unused planetary-constants file no longer downloaded |
| v2 | Direction test runs first; no 360.0 values; `--start`, `--days`, `--step`; size estimate; `step_hours` |
| v1 | First version |

## Open items

| Item | Owner |
| --- | --- |
| Run on IoT's real sites.csv and share sky.npz via Google Drive | CE 2 |
| NASA map comparison: Ash runs the engine at the 100 NASA pixels (`scripts/validate_pgda.py`), CE 2 runs the 18.6-year command above for the same pixels, CE 3 compares | Ash, CE 2, CE 3 |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `spiceypy is missing` / `skyfield is missing` | Run `pip install -r requirements.txt` first |
| `Could not download ...` or `looks incomplete` | Delete that file from `data/kernels/`, download it by hand from the NASA link shown, run again |
| `sites.csv is missing column(s)` | Check the input table above and send the message to IoT |
| `check 0 FAIL` | Stop. Don't send anything to CE 3; tell the team |
| CE 3 says sunlight looks wrong | Check CE 3 reads `sun_az` as θ (map convention), not as a compass bearing |

## Sources

- NASA NAIF, The SPICE Toolkit and generic kernels: https://naif.jpl.nasa.gov
- SpiceyPy: https://github.com/AndrewAnnex/SpiceyPy
- Skyfield (independent check): https://rhodesmill.org/skyfield
- NASA PDS Geosciences Node, LRO LOLA polar elevation maps (frame and 1,737.4 km sphere)
- NASA PGDA lunar illumination maps: https://pgda.gsfc.nasa.gov
- Team docs: `docs/landing-site-algorithm.pdf` (Step 2), `docs/ash-study-guide.md` (section 3.10),
  `horizon/dem.py`, `horizon/reference.py`, `tests/test_dem.py`
