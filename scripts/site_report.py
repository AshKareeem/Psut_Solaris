"""One site's detail for the web app (official objectives 3-5, findings I, J, L): the skyline, the hourly Sun and
Earth tracks, events, battery and a plain-English verdict with the reason behind each dark or silent spell.

Written per top site by scripts/score_sites.py (sites/<id>.json) and for any coordinates by scripts/analyze.py,
so both give the same file for the same inputs. Schema: docs/ui-data-contract.md.
Directions are the team convention (theta from map +x, counterclockwise); bearings in the text are compass
bearings, clockwise from local north.
"""
import numpy as np

from scripts.battery import levels, simulate
from scripts.events import earth_clearance, site_events, skyline_at, sun_clearance, sun_fraction

VERSION = 1


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


def blocked_by(H, D, theta, el, lon):
    """Why a body at map direction theta and elevation el (degrees) is hidden, in words."""
    j = int(round(theta * H.size / 360)) % H.size
    sky = float(skyline_at(H[None], np.array([[theta]]))[0, 0])
    where = f"bearing {bearing(theta, lon):.0f} deg"
    if sky <= 0:
        return f"it is below the Moon's own curvature ({where}, horizon {sky:.2f} deg)"
    far = f"{D[j] / 1e3:.1f} km" if D[j] >= 1000 else f"{D[j]:.0f} m"
    return f"terrain {far} away blocks it ({where}: skyline {sky:.2f} deg, centre of the body at {el:.2f} deg)"


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

    summary = {
        "touchdown_sun": bool(lit[0]), "touchdown_earth": bool(e[0]), "safe_landing": bool(both[0] and survives),
        "survives": bool(survives), "dies_at_hour": None if survives else int(death),
        "battery_lowest_Wh": round(lowest, 1),
        "f_sun": round(float(lit.mean()), 3), "f_earth": round(float(e.mean()), 3), "f_both": round(float(both.mean()), 3),
        "longest_dark_h": int(dark_h), "bridge_Wh": round(battery.energy_to_bridge(dark_h), 1),
        "longest_earth_blackout_h": int(quiet_h)}

    side = lambda c: f"{abs(c):.2f} deg {'above' if c > 0 else 'below'} the skyline"
    verdict = [
        f"Touchdown {utc(0)} UTC: the Sun's centre is {side(sun_c[0])} and the top of Earth's disc {side(earth_c[0])} "
        f"({'power and a link at landing' if both[0] else 'no power at landing' if not lit[0] else 'no Earth link at landing'}).",
        f"Over {hours / 24:g} days: Sun up {lit.mean():.0%}, Earth in view {e.mean():.0%}, both {both.mean():.0%} of the time.",
        (f"Survives the mission: the battery never drops below {battery.e_min:g} Wh (lowest {lowest:.0f} Wh)."
         if survives else
         f"The battery drops below {battery.e_min:g} Wh after {int(death) + 1} h (day {int(death) // 24 + 1})."),
        (f"Longest darkness {dark_h} h: that is the cold soak; at {battery.p_load:g} W it takes "
         f"{battery.energy_to_bridge(dark_h):.0f} Wh to bridge (the battery holds {battery.e_max - battery.e_min:.0f} Wh above its floor)."
         if dark_h else "No darkness during the mission: no cold soak."),
        "Battery model: power = panel power x visible Sun, whatever the Sun's direction (a sun-tracking array), "
        "so survival is an upper bound for fixed panels."]
    why = []
    if dark_h:
        k = dark_start + dark_h // 2
        why.append(f"Darkest spell from {utc(dark_start)} UTC ({dark_h} h): "
                   + blocked_by(H, D, float(track["sun_az"][k]), float(track["sun_el"][k]), site["lon"]) + ".")
    if quiet_h:
        k = quiet_start + quiet_h // 2
        why.append(f"Longest Earth blackout from {utc(quiet_start)} UTC ({quiet_h} h): "
                   + blocked_by(H, D, float(track["earth_az"][k]), float(track["earth_el"][k]), site["lon"]) + ".")
    if not complete.all():
        why.append(f"{int((~complete).sum())} of {complete.size} directions left the terrain map before the full "
                   "range: the skyline there may be too low.")

    return {
        "version": VERSION, "site": site, "mast_m": mast, "earth_margin_deg": earth_margin,
        "mission": {"start_utc": utc(0), "hours": hours},
        "summary": summary, "verdict": verdict, "why": why,
        "events": site_events(sun_c, earth_c, t0),
        "skyline": {"theta_deg": r(np.arange(H.size) * 360.0 / H.size), "horizon_deg": r(H, 3),
                    "blocker_km": r(D / 1e3), "complete": [bool(v) for v in complete]},
        "hourly": {"time_utc": [utc(h) for h in range(hours)],
                   "sun_az": r(track["sun_az"]), "sun_el": r(track["sun_el"], 3), "sun_clearance_deg": r(sun_c, 3),
                   "earth_az": r(track["earth_az"]), "earth_el": r(track["earth_el"], 3),
                   "earth_clearance_deg": r(earth_c, 3), "sun_fraction": r(s),
                   "earth_visible": [bool(v) for v in e], "battery_Wh": r(levels(s, battery), 1)}}
