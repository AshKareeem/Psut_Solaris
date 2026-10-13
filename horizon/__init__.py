"""Horizon engine for the CLPS Lunar Mission Browser (NASA Space Apps 2026)."""

# Engine settings from scripts/convergence.py (Oct 13, 2026), 240 m map alone and 20 m + 240 m: every site's skyline
# within 0.02 deg of the finest settings in 99% of its directions, and Sun and Earth visibility per site within 0.1
# percentage point. Re-run the study whenever the terrain changes.
N_AZ = 1440        # azimuths, 0.25 deg apart; 720 fails (0.022 deg at the worst site)
D_MAX = 250_000.0  # m; 200 km misses distant massifs (a whole sector off by up to 0.8 deg); nothing changes beyond 250 km
KAPPA = 0.002      # step factor: step = max(pixel/2, KAPPA * d)
D_FINE = 40_000.0  # m: with a fine map, it serves this far around each site and the coarse map beyond; 20 km fails
