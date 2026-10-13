"""Horizon engine for the CLPS Lunar Mission Browser (NASA Space Apps 2026)."""

# Engine settings from scripts/convergence.py on the 240 m map (Oct 13, 2026): every skyline within 0.02 deg of the
# finest settings tested. Re-run the study whenever the terrain changes (20 m near field, Phase 5).
N_AZ = 2880        # azimuths, 0.125 deg apart
D_MAX = 250_000.0  # m; 150 km misses massifs that form parts of the skyline (up to 1.4 deg)
KAPPA = 0.002      # step factor: step = max(pixel/2, KAPPA * d)
