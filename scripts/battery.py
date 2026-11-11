"""Battery model (IoT, Step 4): an hour-by-hour energy budget for a solar-powered lander.

  E(t+1) = min(e_max, E(t) + (p_panel * s(t) - p_load) * dt), never below 0; the lander starts full and
  survives if E never drops below e_min. s(t) is the visible fraction of the Sun (Step 3).

Default numbers (IoT, battery_v2):
  p_panel = 200 W   max solar power of the Nova-C lander (Wikipedia)
  e_max   = 700 Wh  25 Ah x 28 V (calculated)
  p_load  = 50 W    ESTIMATE, from Odysseus lasting 10-20 hours on battery (Reuters)
  e_min   = 140 Wh  ASSUMPTION, 20% of a full battery
With these, a full battery bridges (e_max - e_min) / p_load = 11.2 hours without sunlight.
"""
from dataclasses import dataclass

import numpy as np


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


def simulate(sun, battery):
    """sun [..., hours]: visible fraction of the Sun each hour (any leading shape, views are fine).
    Returns the lowest level reached (Wh) and the first hour the level is below e_min (-1 if never), shape [...]."""
    level = np.full(sun.shape[:-1], battery.e_max)
    lowest = level.copy()
    death = np.full(sun.shape[:-1], -1)
    for h in range(sun.shape[-1]):
        level = _step(level, sun[..., h], battery)
        lowest = np.minimum(lowest, level)
        death = np.where((death < 0) & (level < battery.e_min), h, death)
    return lowest, death


def levels(sun, battery):
    """Battery level (Wh) after every hour, for one site's timeline."""
    level, out = np.float64(battery.e_max), []
    for s in sun:
        level = _step(level, s, battery)
        out.append(float(level))
    return out


def _step(level, sun, battery):
    return np.clip(level + (battery.p_panel * sun - battery.p_load) * battery.dt, 0.0, battery.e_max)
