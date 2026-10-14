import numpy as np

R = 1_737_400.0  # m, radius of the LOLA reference sphere


def step_schedule(pixel, d_max, kappa):
    """Distances along a ray: half-pixel steps near the site, steps ~ kappa*d far away."""
    d = [pixel / 2]
    while d[-1] < d_max:
        d.append(d[-1] + max(pixel / 2, kappa * d[-1]))
    return np.array(d)


def bilinear(dem, col, row):
    """Sample dem at fractional (col, row). NaN outside the grid."""
    nr, nc = dem.shape
    c0 = np.floor(col).astype(int)
    r0 = np.floor(row).astype(int)
    ok = (c0 >= 0) & (r0 >= 0) & (c0 < nc - 1) & (r0 < nr - 1)
    c0 = np.where(ok, c0, 0)
    r0 = np.where(ok, r0, 0)
    fc, fr = col - c0, row - r0
    z = (dem[r0, c0] * (1 - fc) * (1 - fr) + dem[r0, c0 + 1] * fc * (1 - fr)
         + dem[r0 + 1, c0] * (1 - fc) * fr + dem[r0 + 1, c0 + 1] * fc * fr)
    return np.where(ok, z, np.nan)


def horizon_profile(terrain, x0, y0, mast, d_max, n_az, kappa):
    """Horizon elevation H (deg), blocker distance (m) and completeness flag for one site at map (x0, y0) metres."""
    theta = np.arange(n_az) * (2 * np.pi / n_az)        # from map +x, counterclockwise
    d = step_schedule(terrain.levels[0].pixel, d_max, kappa)
    terrain.check_coverage(np.array([x0]), np.array([y0]), d)
    level = terrain.level_of(d)
    z = np.empty((n_az, d.size))
    for i, dem in enumerate(terrain.levels):           # each level samples its own stretch of every ray
        k = level == i
        row0, col0 = dem.xy_to_rowcol(x0, y0)
        cols = col0 + np.outer(np.cos(theta), d[k]) / dem.pixel
        rows = row0 - np.outer(np.sin(theta), d[k]) / dem.pixel    # map +y = smaller row index
        z[:, k] = bilinear(dem.height, cols, rows)
    row0, col0 = terrain.levels[0].xy_to_rowcol(x0, y0)
    z0 = float(bilinear(terrain.levels[0].height, col0, row0))
    if np.isnan(z0):
        raise ValueError(f"site at x {x0:.0f} m, y {y0:.0f} m is on a no-data pixel")
    r_obs = R + z0 + mast
    phi = d / R                                         # central angle to each sample
    r_pt = R + z
    up = r_pt * np.cos(phi) - r_obs                     # height above the observer's level
    out = r_pt * np.sin(phi)                            # horizontal distance
    ratio = np.where(np.isnan(z), -np.inf, up / out)    # tan(angle); max ratio = max angle
    k = np.argmax(ratio, axis=1)
    H = np.degrees(np.arctan(ratio[np.arange(n_az), k]))
    complete = ~np.isnan(z[:, -1])                      # False if the ray left the DEM
    return H, d[k], complete
