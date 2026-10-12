"""Estimate the fraction of a year with some sunlight above the horizon."""

import numpy as np


H = np.load("out/rim_H.npy")
e = 1.54 * np.sin(2 * np.pi * np.arange(365) / 365)
s = np.clip((e[:, None] - H[None, :] + 0.27) / 0.54, 0, 1)
print(f"sunlit fraction of the year: {s.mean():.0%}")
