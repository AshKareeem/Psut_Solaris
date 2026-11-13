"""Events at one site from hourly Sun and Earth tracks (official objectives 3 and 4): when the Sun and Earth rise
and set over the skyline, direct-to-Earth (DTE) windows, time left before sunset or Earthset, and how high the
Sun stands above the skyline.

  sun clearance   = sun_el - H(sun_az)                          > 0: more than half the Sun visible (s > 0.5)
  earth clearance = earth_el + r_earth - H(earth_az) - margin   > 0: Earth in view (e), as in Step 3
Each event time is the linear zero crossing of the clearance between two hourly samples, given to the minute.
An interval already under way at the first sample has start None; one still going at the last sample has end None.
"""
import numpy as np


def skyline_at(H, az):
    """H [..., n_az] interpolated between neighbouring directions at az [..., hours] (degrees)."""
    n_az = H.shape[-1]
    pos = (np.asarray(az) % 360) * (n_az / 360)
    j0 = np.floor(pos).astype(int) % n_az
    frac = pos - np.floor(pos)
    h0 = np.take_along_axis(H, j0, axis=-1)
    h1 = np.take_along_axis(H, (j0 + 1) % n_az, axis=-1)
    return h0 * (1 - frac) + h1 * frac


def sun_fraction(sun_c, sun_radius):
    """Visible fraction of the Sun's disc from its clearance (team PDF, Step 3)."""
    return np.clip((sun_c + sun_radius) / (2 * sun_radius), 0, 1)


def sun_clearance(H, sun_az, sun_el):
    """Degrees the Sun's centre stands above the skyline (negative: below it)."""
    return sun_el - skyline_at(H, sun_az)


def earth_clearance(H, earth_az, earth_el, earth_radius, margin):
    """Degrees the top of Earth's disc stands above the skyline plus the antenna margin (negative: hidden)."""
    return earth_el + earth_radius - skyline_at(H, earth_az) - margin


def intervals(clearance):
    """[(start, end)] in hours from the first sample where clearance > 0; start/end None past the series' ends."""
    up = clearance > 0
    k = np.flatnonzero(up[1:] != up[:-1])                     # a crossing lies between samples k and k + 1
    t = k + clearance[k] / (clearance[k] - clearance[k + 1])
    starts, ends = list(t[up[k + 1]]), list(t[~up[k + 1]])
    if up[0]:
        starts.insert(0, None)
    if up[-1]:
        ends.append(None)
    return list(zip(starts, ends))


def overlap(a, b):
    """Intersection of two interval lists (None = beyond the series)."""
    lo = lambda v: -np.inf if v is None else v
    hi = lambda v: np.inf if v is None else v
    out = []
    for s1, e1 in a:
        for s2, e2 in b:
            s, e = max(lo(s1), lo(s2)), min(hi(e1), hi(e2))
            if s < e:
                out.append((None if s == -np.inf else s, None if e == np.inf else e))
    return out


def until_end(spans, t):
    """Hours from t to the end of the span containing t: 0 if t is outside every span, None if beyond the series."""
    for s, e in spans:
        if (s is None or s <= t) and (e is None or t < e):
            return None if e is None else e - t
    return 0.0


def to_utc(t, t0):
    """Hours after t0 (numpy datetime64) as 'YYYY-MM-DDTHH:MM', None stays None."""
    return None if t is None else str(t0 + np.timedelta64(int(round(t * 60)), "m"))


def site_events(sun_c, earth_c, t0):
    """Sunlit, DTE and both-at-once windows (UTC, to the minute), and the time left from the first sample."""
    sun, earth = intervals(sun_c), intervals(earth_c)
    both = overlap(sun, earth)
    utc = lambda spans: [{"start": to_utc(s, t0), "end": to_utc(e, t0)} for s, e in spans]
    left = lambda v: None if v is None else round(v, 2)
    return {"sunlit": utc(sun), "dte": utc(earth), "both": utc(both),
            "hours_to_sunset": left(until_end(sun, 0.0)), "hours_to_earthset": left(until_end(earth, 0.0))}
