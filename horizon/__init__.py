"""Horizon engine for the CLPS Lunar Mission Browser (NASA Space Apps 2026)."""

# Engine settings from scripts/convergence.py (Oct 14, 2026): the cheapest settings where every site's skyline is
# within 0.02 deg of the finest settings in 99% of its directions (240 m map: rim + 500 sites within 5 deg, against
# 11520 azimuths, 300 km, kappa 0.00025; 20 m + 240 m: rim + 150 sites within 0.43 deg). Re-run when the terrain changes.
N_AZ = 1440        # azimuths, 0.25 deg apart; 720 fails (0.023 deg at the worst site)
D_MAX = 250_000.0  # m; 200 km misses distant massifs (worst site 0.68 deg off in 99% of its directions); 300 km changes nothing
KAPPA = 0.002      # step factor: step = max(pixel/2, KAPPA * d)
D_FINE = 40_000.0  # m: with a fine map, it serves this far around each site and the coarse map beyond; 20 km fails
