"""Horizon engine for the CLPS Lunar Mission Browser (NASA Space Apps 2026)."""

# Engine settings from scripts/convergence.py on the 240 m map (Oct 13, 2026): every skyline within 0.02 deg of the
# finest settings tested (worst 0.012 deg over 501 sites). Re-run the study whenever the terrain changes (Phase 5).
N_AZ = 5760        # azimuths, 0.0625 deg apart; 2880 misses 0.02 deg in about one direction per million
D_MAX = 250_000.0  # m; 200 km still misses distant massifs (up to 0.8 deg); nothing changes beyond 250 km
KAPPA = 0.002      # step factor: step = max(pixel/2, KAPPA * d)
