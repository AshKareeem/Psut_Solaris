# IM-1 replay: the tool against a real landing

Intuitive Machines' Odysseus (IM-1) landed on 22 February 2024 at about 80.13°S, 1.44°E, near Malapert A. It tipped over by about 30°, with its solar panels facing the wrong way, and lost power on 29 February as the Sun sank low.

```
python scripts/analyze.py --lat -80.13 --lon 1.44 --mast 2 --start 2024-02-22T23 --days 10 --coarse data/ldem_75s_240m.lbl --id IM-1 --out out/analyze/im1_m2.json
```

What the tool says (240 m terrain only, NASA SPICE sky, 2 m mast):

| Date (UTC) | Sun above the level horizon | Sun above the skyline | Earth elevation |
|---|---|---|---|
| 22 Feb 23:00 (touchdown) | 10.5° | +10.3° | 15.4° |
| 29 Feb 00:00 | 6.6° | +5.4° | 8.2° |
| 29 Feb 12:00 | 5.7° | +4.7° | 7.5° |
| 2 Mar 14:17 | | **terrain sunset** (terrain 2.5 km away, bearing 265°) | 4.9° |

- Earth stays in view for the whole 10 days, so the direct-to-Earth link was never the limit.
- The terrain sets the Sun on 2 March at 14:17 UTC. When Odysseus died on 29 February, the Sun was still about 5° above the skyline.
- **So terrain did not end IM-1; its attitude did.** A tipped lander with fixed panels loses the low Sun days before sunset. That is why our battery model calls its survival an upper bound (sun-tracking array), and why the headline is the longest darkness and the energy to bridge it, which need no panel geometry.

Limits, stated plainly:

- IM-1 is about 300 km from the pole. That's outside every 20 m map on disk (`ldem_875s_20m` reaches 76 km; `ldem_80s_20m` would reach it but leaves less than the 40 km fine margin), so this run uses the 240 m map only.
- 411 of 1,440 directions (northward, away from the pole) leave the 240 m map before 250 km. The report flags them. The skyline toward the Sun at sunset (bearing 265°, terrain 2.5 km away) is complete.
- The exact time Odysseus stopped is not public to the hour, so this is a check of timing to within days, not hours.

Sources: [Universe Today: Lunar Night Permanently Ends the Odysseus Mission](https://www.universetoday.com/articles/lunar-night-permanently-ends-the-odysseus-mission) · [Rappler: Odysseus goes dormant (29 Feb 2024; "the sun sank low on the lunar horizon"; panels "facing the wrong direction")](https://www.rappler.com/science/earth-space/moon-lander-odysseus-dormant-february-2024/) · [IM-1 (Wikipedia)](https://en.wikipedia.org/wiki/IM-1)
