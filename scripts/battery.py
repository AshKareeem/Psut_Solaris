"""Battery model (IoT, Step 4): an hour-by-hour energy budget for a solar-powered lander.

  E(t+1) = min(e_max, E(t) + (p_panel * s(t) - p_load) * dt), never below 0; the lander starts full and
  survives if E never drops below e_min. s(t) is the visible fraction of the Sun (Step 3).

Default numbers (IoT, battery_v2):
  p_panel = 200 W   max solar power of the Nova-C lander (Wikipedia)
  e_max   = 700 Wh  25 Ah x 28 V (calculated)
  p_load  = 50 W    ESTIMATE, from Odysseus lasting 10-20 hours on battery (Reuters)
  e_min   = 140 Wh  ASSUMPTION, 20% of a full battery
With these, a full battery bridges (e_max - e_min) / p_load = 11.2 hours without sunlight.

Power is p_panel times the visible fraction of the Sun, whatever the Sun's direction: that is a sun-tracking
array. Real polar landers carry fixed panels while the Sun circles the horizon every 29.5 days, so survival here
is an upper bound. The headline needs no guessed panel geometry: the longest darkness (the cold soak) and the
energy to bridge it at the user's load, energy_to_bridge(hours).
"""
from dataclasses import dataclass

import numpy as np
from numba import njit, prange

LANDER = {
    "name": "Nova-C class (IoT estimate)",
    "model": "sun-tracking array: power = p_panel x visible Sun fraction, whatever the Sun's direction, so survival "
             "is an upper bound for fixed panels",
    "sources": {"p_panel": "Nova-C max solar power, 200 W (Wikipedia)",
                "e_max": "25 Ah x 28 V (IoT, calculated)",
                "p_load": "ESTIMATE from Odysseus lasting 10-20 hours on battery (Reuters)",
                "e_min": "ASSUMPTION: 20% of a full battery"},
}


@dataclass(frozen=True)
class Battery:
    e_max: float = 700.0    # Wh
    e_min: float = 140.0    # Wh
    p_panel: float = 200.0  # W
    p_load: float = 50.0    # W
    dt: float = 1.0         # h

    def bridge_hours(self):
        """Hours a full battery lasts with no sunlight before it drops below e_min."""
        return (self.e_max - self.e_min) / self.p_load

    def energy_to_bridge(self, hours):
        """Wh the load draws through `hours` without sunlight."""
        return hours * self.p_load

    def profile(self):
        """The lander as results.json states it: numbers, model and sources."""
        return {"name": LANDER["name"], "e_max_Wh": self.e_max, "e_min_Wh": self.e_min, "p_panel_W": self.p_panel,
                "p_load_W": self.p_load, "bridge_hours": self.bridge_hours(), "model": LANDER["model"],
                "sources": LANDER["sources"]}


@njit(cache=True)
def step(level, sun, e_max, p_panel, p_load, dt):
    """One hour of the model: E + (p_panel * s - p_load) * dt, kept between 0 and e_max. The only copy of the
    formula: every function below calls it."""
    return min(max(level + (p_panel * sun - p_load) * dt, 0.0), e_max)


@njit(cache=True)
def _mission(sun, k, hours, e_max, e_min, p_panel, p_load, dt):
    """The mission of `hours` starting at hour k of sun [T]: lowest level and first hour below e_min (-1: never)."""
    level, lowest, death = e_max, e_max, -1
    for h in range(hours):
        level = step(level, sun[k + h], e_max, p_panel, p_load, dt)
        lowest = min(lowest, level)
        if death < 0 and level < e_min:
            death = h
    return lowest, death


@njit(parallel=True, cache=True)
def _windows(sun, hours, e_max, e_min, p_panel, p_load, dt):
    n, starts = sun.shape[0], sun.shape[1] - hours + 1
    lowest, death = np.empty((n, starts), np.float32), np.empty((n, starts), np.int16)
    for i in prange(n):
        for k in range(starts):
            lowest[i, k], death[i, k] = _mission(sun[i], k, hours, e_max, e_min, p_panel, p_load, dt)
    return lowest, death


def _args(battery):
    return battery.e_max, battery.e_min, battery.p_panel, battery.p_load, battery.dt


def simulate(sun, battery):
    """sun [..., hours]: visible fraction of the Sun each hour of one mission (any leading shape).
    Returns the lowest level reached (Wh) and the first hour the level is below e_min (-1 if never), shape [...]."""
    flat = np.ascontiguousarray(sun, np.float64).reshape(-1, sun.shape[-1])
    lowest, death = _windows(flat, sun.shape[-1], *_args(battery))
    return lowest[:, 0].astype(np.float64).reshape(sun.shape[:-1]), death[:, 0].astype(int).reshape(sun.shape[:-1])


def simulate_windows(sun, hours, battery):
    """sun [sites, T]: visible fraction of the Sun each hour of the sky file. For the mission of `hours` that starts
    at every hour k = 0 .. T - hours: lowest level (Wh, float32) and first hour below e_min (int16, -1 if never),
    each [sites, T - hours + 1]."""
    return _windows(np.ascontiguousarray(sun, np.float64), hours, *_args(battery))


def levels(sun, battery):
    """Battery level (Wh) after every hour, for one site's timeline."""
    level, out = float(battery.e_max), []
    for s in sun:
        level = step(level, float(s), battery.e_max, battery.p_panel, battery.p_load, battery.dt)
        out.append(level)
    return out
