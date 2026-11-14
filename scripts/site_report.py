"""One site's detail for the web app (official objectives 3-5, findings I, J, L): the skyline, the hourly Sun and
Earth tracks, events, battery and a plain-English verdict with the reason behind each dark or silent spell.

Written per top site by scripts/score_sites.py (sites/<id>.json) and for any coordinates by scripts/analyze.py,
so both give the same file for the same inputs. Schema: docs/ui-data-contract.md.
Directions are the team convention (theta from map +x, counterclockwise); bearings in the text are compass
bearings, clockwise from local north.
"""
import numpy as np

from scripts.battery import Battery, levels, simulate
from scripts.events import earth_clearance, intervals, site_events, skyline_at, sun_clearance, sun_fraction, to_utc
from scripts.validate_horizons import horizons_url

VERSION = 1
# The submission rules: generated code and data must acknowledge generation in text and metadata.
PROVENANCE = ("Computed by the LunarWindow pipeline from NASA LOLA terrain and NASA SPICE (DE421) ephemerides. "
              "Code written with AI assistance (Claude Code) and verified by the team with automated tests and a "
              "comparison against NASA PGDA illumination maps.")
MARGINAL_DEG = 0.5   # a touchdown clearance under this is marginal: small landing or terrain errors can hide the body


def bearing(theta, lon):
    """Compass bearing (clockwise from local north) of map direction theta at longitude lon, degrees."""
    return (90.0 - lon - theta) % 360.0


def longest_span(flags):
    """(first hour, length) of the longest run of True; (None, 0) if there is none."""
    best, start, run = (None, 0), 0, 0
    for h, f in enumerate(flags):
        run = run + 1 if f else 0
        if f and run == 1:
            start = h
        if run > best[1]:
            best = (start, run)
    return best


def horizon_there(H, D, theta):
    """The skyline height (deg) toward map direction theta, and what forms it, in words."""
    j = int(round(theta * H.size / 360)) % H.size
    sky = float(skyline_at(H[None], np.array([[theta]]))[0, 0])
    if sky <= 0:
        return sky, "the Moon's own curvature"
    return sky, f"terrain {D[j] / 1e3:.1f} km away" if D[j] >= 1000 else f"terrain {D[j]:.0f} m away"


def blocked_by(H, D, theta, el, lon):
    """Why a body at map direction theta and elevation el (degrees) is hidden, in words."""
    sky, what = horizon_there(H, D, theta)
    where = f"bearing {bearing(theta, lon):.0f} deg"
    if sky <= 0:
        return f"it is below the Moon's own curvature ({where}, horizon {sky:.2f} deg)"
    return f"{what} blocks it ({where}: skyline {sky:.2f} deg, centre of the body at {el:.2f} deg)"


def clears(H, D, theta, clearance, lon):
    """How far a visible body clears the skyline toward theta, and what forms the skyline there, in words."""
    sky, what = horizon_there(H, D, theta)
    return f"{clearance:.2f} deg above the skyline (bearing {bearing(theta, lon):.0f} deg, set by {what} at {sky:.2f} deg)"


# ---------------------------------------------------------------------------------------------------------------
# The failsafe blocks (spec commit 2): a contact plan, a verdict per dark spell, and a half-battery what-if.
# Visibility comes from scripts/events.py and the battery from scripts/battery.py; nothing here is new physics.
WEAK_FACTOR = 0.5
WEAK_LABEL = "assumption: half the battery, e.g. a cell lost or a cold battery"


def contact_plan_block(earth_c, t0, hours, longest_blackout_h):
    """The Earth-contact windows (events.intervals on the same clearance as events.dte) that cover touchdown, the
    mission's middle hour and its last hour; the first contact at or after touchdown; what has no window."""
    spans = intervals(np.asarray(earth_c))
    holds = lambda span, t: (span[0] is None or span[0] <= t) and (span[1] is None or t < span[1])
    covers, order, missing = {}, [], []
    for name, t in (("touchdown", 0.0), ("mid-mission", hours / 2), ("end", hours - 1.0)):
        span = next((sp for sp in spans if holds(sp, t)), None)
        if span is None:
            missing.append(name)
        else:
            if span not in covers:
                covers[span], _ = [], order.append(span)
            covers[span].append(name)
    first = None if not spans else to_utc(0.0 if spans[0][0] is None else spans[0][0], t0)
    return {"first_contact_utc": first,
            "windows": [{"start": to_utc(a, t0), "end": to_utc(b, t0), "covers": covers[(a, b)]} for a, b in order],
            "missing": missing, "longest_blackout_h": int(longest_blackout_h)}


def dark_verdict_block(lit, battery_Wh, battery, utc):
    """One entry per run of hours with the Sun at or under half (s <= 0.5), from the battery level series the
    report already carries: when it starts, its first hour after (end), the level entering it, the lowest inside,
    and whether the level stays at or above e_min right through (lasts). [] when the Sun never sets."""
    out, h, n = [], 0, len(lit)
    while h < n:
        if lit[h]:
            h += 1
            continue
        start = h
        while h < n and not lit[h]:
            h += 1
        lowest = min(battery_Wh[start:h])
        out.append({"start": utc(start), "end": utc(h), "hours": h - start,
                    "battery_start_Wh": round(battery_Wh[start - 1] if start else battery.e_max, 1),
                    "battery_lowest_Wh": round(lowest, 1), "lasts": bool(lowest >= battery.e_min)})
    return out


def weak_battery_block(s, battery, factor=WEAK_FACTOR):
    """The same mission through battery.simulate with the capacity scaled by `factor`; the reserve scales too, so
    it stays 20% of a full battery, as battery.py defines it. Panel and load are unchanged."""
    b = Battery(battery.e_max * factor, battery.e_min * factor, battery.p_panel, battery.p_load, battery.dt)
    lowest, death = (float(v) for v in simulate(np.asarray(s, float), b))
    return {"capacity_factor": factor, "e_max_Wh": b.e_max, "e_min_Wh": b.e_min,
            "survives": bool(death < 0), "dies_at_hour": None if death < 0 else int(death), "label": WEAK_LABEL}


def failsafe_words(cp, dark, weak, battery, utc, hours):
    """The three blocks in plain English. Every survives/lasts claim says "at best (sun-tracking panels)"."""
    words = []
    if cp["first_contact_utc"] is None:
        words.append("Earth is never in view during the mission: no plan can be uploaded.")
    elif not cp["missing"]:
        words.append(f"Earth in view at touchdown, mid-mission and end: upload the plan at landing and confirm it "
                     f"on {utc(hours // 2)[:10]}.")
    else:
        words.append(f"No Earth contact at {' or '.join(cp['missing'])}: first contact "
                     f"{cp['first_contact_utc']} UTC, longest blackout {cp['longest_blackout_h']} h.")
    if not dark:
        words.append("No darkness during the mission.")
    else:
        bad = next((r for r in dark if not r["lasts"]), None)
        head = f"{len(dark)} dark spell{'s' if len(dark) > 1 else ''}, the longest {max(r['hours'] for r in dark)} h"
        if bad is None:
            words.append(f"{head}; the battery lasts through every one, at best (sun-tracking panels).")
        else:
            words.append(f"{head}; the battery does not last through the spell starting {bad['start']} UTC: even "
                         f"at best (sun-tracking panels) it drops below {battery.e_min:g} Wh.")
    words.append("With half the battery it still survives, at best (sun-tracking panels)." if weak["survives"]
                 else f"With half the battery it dies at hour {weak['dies_at_hour']} "
                      f"({utc(weak['dies_at_hour'])} UTC), even at best (sun-tracking panels).")
    return words


# The confidence block (spec commit 3): what the convergence study's skyline bound does to this mission.
SKYLINE_SHIFT_DEG = 0.02   # the convergence study: every site within 0.02 deg in 99% of its directions
CHECKS = ["Sun and Earth positions: 124 checked against NASA JPL Horizons, all within 0.0003 deg.",
          "Sunlight: matches NASA's PGDA map at the Shackleton rim, correlation 0.92 (2 m best fit)."]
CANNOT_SEE = ["Hazards smaller than the 20 m map, like the ~20 m crater IM-2 tipped into.",
              "A tilted lander with fixed panels, like IM-1: survival here is an upper bound."]


def first_set(clearance):
    """Hours from the first sample to the first downward crossing (events.intervals); None if the body never sets
    inside the mission."""
    return next((end for _, end in intervals(np.asarray(clearance)) if end is not None), None)


def shifted_clearances(H, track, earth_margin, delta):
    """The mission's Sun and Earth clearances with the whole skyline shifted by delta degrees: the same
    events.py functions on H + delta."""
    sun_c = sun_clearance((H + delta)[None], track["sun_az"][None], track["sun_el"])[0]
    earth_c = earth_clearance((H + delta)[None], track["earth_az"][None], track["earth_el"],
                              track["earth_radius_deg"], earth_margin)[0]
    return sun_c, earth_c


def safe_landing_with(H, track, battery, earth_margin, delta):
    """summary.safe_landing recomputed with the skyline shifted by delta: the same visibility and battery code."""
    sun_c, earth_c = shifted_clearances(H, track, earth_margin, delta)
    s = sun_fraction(sun_c, track["sun_radius_deg"])
    _, death = simulate(s, battery)
    return bool((s[0] > 0.5) and (earth_c[0] > 0) and (int(death) < 0))


def confidence_block(H, track, battery, earth_margin, delta=SKYLINE_SHIFT_DEG):
    """How much the first sunset and Earthset move, and whether the safe-landing verdict flips, when the skyline
    is raised and lowered by delta (the larger shift of the two); plus the static checks and blind spots."""
    def shift_min(pick):
        base = pick(0.0)
        if base is None:
            return None
        moved = [abs(t - base) * 60 for t in (pick(delta), pick(-delta)) if t is not None]
        return round(max(moved), 1) if moved else None

    sets = {d: shifted_clearances(H, track, earth_margin, d) for d in (0.0, delta, -delta)}
    return {"skyline_shift_deg": delta,
            "sunset_shift_min": shift_min(lambda d: first_set(sets[d][0])),
            "earthset_shift_min": shift_min(lambda d: first_set(sets[d][1])),
            "verdict_changes": bool(any(safe_landing_with(H, track, battery, earth_margin, d)
                                        != safe_landing_with(H, track, battery, earth_margin, 0.0)
                                        for d in (delta, -delta))),
            "checks": list(CHECKS), "cannot_see": list(CANNOT_SEE)}


def nasa_check_block(site, t0, sun_el, earth_el):
    """Links to NASA JPL Horizons' own table of the Sun and Earth seen from this site at the landing hour (the query
    scripts/validate_horizons.py uses for its 124 checks), beside our elevations, so anyone can verify them."""
    return {"landing_utc": t0, "our_sun_el_deg": round(float(sun_el), 4), "our_earth_el_deg": round(float(earth_el), 4),
            "horizons_sun_url": horizons_url("sun", site["lat"], site["lon"], [t0], fmt="text"),
            "horizons_earth_url": horizons_url("earth", site["lat"], site["lon"], [t0], fmt="text"),
            "how": "Open a link: NASA JPL Horizons lists azimuth and elevation in degrees at this site and hour; "
                   "compare its elevation with ours (Horizons' azimuth is clockwise from north)."}


def site_report(site, H, D, complete, track, mast, battery, earth_margin):
    """site: id, lat, lon, x_m, y_m; H, D, complete: [n_az] at this mast; track: the mission's hourly Sun and Earth
    (time_utc, sun_az, sun_el, earth_az, earth_el, sun_radius_deg, earth_radius_deg). Returns a JSON-ready dict."""
    hours = track["sun_az"].size
    sun_c = sun_clearance(H[None], track["sun_az"][None], track["sun_el"])[0]
    earth_c = earth_clearance(H[None], track["earth_az"][None], track["earth_el"], track["earth_radius_deg"],
                              earth_margin)[0]
    s, e = sun_fraction(sun_c, track["sun_radius_deg"]), earth_c > 0
    lit, both = s > 0.5, (s > 0.5) & e
    lowest, death = (float(v) for v in simulate(s, battery))
    survives = death < 0
    dark_start, dark_h = longest_span(~lit)
    quiet_start, quiet_h = longest_span(~e)
    t0 = np.datetime64(str(track["time_utc"][0]))
    utc = lambda h: str(t0 + np.timedelta64(int(h), "h"))[:13]
    r = lambda a, n=2: [round(float(v), n) for v in a]
    battery_Wh = levels(s, battery)

    near = [name for name, up, c in (("the Sun's centre", lit[0], sun_c[0]), ("the top of Earth's disc", e[0], earth_c[0]))
            if up and c < MARGINAL_DEG]
    summary = {
        "touchdown_sun": bool(lit[0]), "touchdown_earth": bool(e[0]), "safe_landing": bool(both[0] and survives),
        "survives": bool(survives), "dies_at_hour": None if survives else int(death),
        "battery_lowest_Wh": round(lowest, 1),
        "f_sun": round(float(lit.mean()), 3), "f_earth": round(float(e.mean()), 3), "f_both": round(float(both.mean()), 3),
        "longest_dark_h": int(dark_h), "battery_used_Wh": round(battery.e_max - lowest, 1),
        "longest_earth_blackout_h": int(quiet_h), "marginal": bool(near)}

    side = lambda c: f"{abs(c):.2f} deg {'above' if c > 0 else 'below'} the skyline"
    verdict = [
        f"Touchdown {utc(0)} UTC: the Sun's centre is {side(sun_c[0])} and the top of Earth's disc {side(earth_c[0])} "
        f"({'power and a link at landing' if both[0] else 'no power at landing' if not lit[0] else 'no Earth link at landing'}).",
        f"Over {hours / 24:g} days: Sun up {lit.mean():.0%}, Earth in view {e.mean():.0%}, both {both.mean():.0%} of the time.",
        (f"Survives the mission: the battery never drops below {battery.e_min:g} Wh (lowest {lowest:.0f} Wh)."
         if survives else
         f"The battery drops below {battery.e_min:g} Wh after {int(death) + 1} h (day {int(death) // 24 + 1})."),
        (f"Longest darkness {dark_h} h: that is the cold soak." if dark_h else
         "No darkness during the mission: no cold soak."),
        (f"Battery used on this mission: {battery.e_max - lowest:.0f} Wh of the {battery.e_max - battery.e_min:.0f} "
         f"Wh it can use above its {battery.e_min:g} Wh floor." if survives else
         f"Battery used on this mission: more than the {battery.e_max - battery.e_min:.0f} Wh it can use above its "
         f"{battery.e_min:g} Wh floor (it drains to {lowest:.0f} Wh)."),
        "Battery model: power = panel power x visible Sun, whatever the Sun's direction (a sun-tracking array), "
        "so survival is an upper bound for fixed panels."]
    why = []
    if near:
        body = "Sun" if near[0].startswith("the Sun") else "Earth"
        az = float(track["sun_az" if body == "Sun" else "earth_az"][0])
        c = float(sun_c[0] if body == "Sun" else earth_c[0])
        why.append(f"Marginal touchdown: {' and '.join(near)} clears the skyline by under {MARGINAL_DEG} deg; "
                   f"{'the Sun' if body == 'Sun' else 'Earth'} is " + clears(H, D, az, c, site["lon"])
                   + ", so there is almost no margin for a landing error, a lower antenna or a later hour.")
    if dark_h:
        k = dark_start + dark_h // 2
        why.append(f"Darkest spell from {utc(dark_start)} UTC ({dark_h} h): "
                   + blocked_by(H, D, float(track["sun_az"][k]), float(track["sun_el"][k]), site["lon"]) + ".")
    if quiet_h:
        k = quiet_start + quiet_h // 2
        why.append(f"Longest Earth blackout from {utc(quiet_start)} UTC ({quiet_h} h): "
                   + blocked_by(H, D, float(track["earth_az"][k]), float(track["earth_el"][k]), site["lon"]) + ".")
    if not dark_h:
        k = int(np.argmin(sun_c))
        why.append(f"The Sun stays up all mission: its closest pass, {utc(k)} UTC, is "
                   + clears(H, D, float(track["sun_az"][k]), float(sun_c[k]), site["lon"]) + ".")
    if not quiet_h:
        k = int(np.argmin(earth_c))
        why.append(f"Earth stays in view all mission: its closest pass, {utc(k)} UTC, is "
                   + clears(H, D, float(track["earth_az"][k]), float(earth_c[k]), site["lon"]) + ".")
    if not complete.all():
        why.append(f"{int((~complete).sum())} of {complete.size} directions left the terrain map before the full "
                   "range: the skyline there may be too low.")

    return {
        "version": VERSION, "provenance": PROVENANCE, "site": site, "mast_m": mast, "earth_margin_deg": earth_margin,
        "mission": {"start_utc": utc(0), "hours": hours},
        "summary": summary, "verdict": verdict, "why": why,
        "contact_plan": (cp := contact_plan_block(earth_c, t0, hours, quiet_h)),
        "dark_verdict": (dark := dark_verdict_block(lit, battery_Wh, battery, utc)),
        "weak_battery": (weak := weak_battery_block(s, battery)),
        "words": failsafe_words(cp, dark, weak, battery, utc, hours),
        "confidence": confidence_block(H, track, battery, earth_margin),
        "nasa_check": nasa_check_block(site, utc(0), track["sun_el"][0], track["earth_el"][0]),
        "events": site_events(sun_c, earth_c, t0),
        "skyline": {"theta_deg": r(np.arange(H.size) * 360.0 / H.size), "horizon_deg": r(H, 3),
                    "blocker_km": r(D / 1e3), "complete": [bool(v) for v in complete]},
        "hourly": {"time_utc": [utc(h) for h in range(hours)],
                   "sun_az": r(track["sun_az"]), "sun_el": r(track["sun_el"], 3), "sun_clearance_deg": r(sun_c, 3),
                   "earth_az": r(track["earth_az"]), "earth_el": r(track["earth_el"], 3),
                   "earth_clearance_deg": r(earth_c, 3), "sun_fraction": r(s),
                   "earth_visible": [bool(v) for v in e], "battery_Wh": r(battery_Wh, 1)}}
