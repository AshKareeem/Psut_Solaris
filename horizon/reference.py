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


def site_frame(x0, y0):
    """Unit vectors (Moon body frame) for sites at map x0, y0: the site itself, and the true directions of map +x
    and map +y there. The map is conformal, so map direction theta is cos(theta)*ex + sin(theta)*ey on the ground."""
    x0, y0 = np.asarray(x0, dtype=np.float64), np.asarray(y0, dtype=np.float64)
    lat = 2 * np.arctan(np.hypot(x0, y0) / (2 * R)) - np.pi / 2
    lon = np.arctan2(x0, y0)
    p0 = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)
    north = np.stack([-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)], axis=-1)
    east = np.stack([-np.sin(lon), np.cos(lon), np.zeros_like(lon)], axis=-1)
    ex = np.sin(lon)[..., None] * north + np.cos(lon)[..., None] * east
    ey = np.cos(lon)[..., None] * north - np.sin(lon)[..., None] * east
    return p0, ex, ey


def great_circle_xy(p0, t, cos_p, sin_p):
    """Map x, y (m) of the point at central angle phi along the great circle leaving p0 in unit direction t.
    South polar stereographic: x = 2R*py/(1 - pz), y = 2R*px/(1 - pz)."""
    px = p0[0] * cos_p + t[0] * sin_p
    py = p0[1] * cos_p + t[1] * sin_p
    pz = p0[2] * cos_p + t[2] * sin_p
    f = 2 * R / (1 - pz)
    return py * f, px * f


def horizon_profile(terrain, x0, y0, mast, d_max, n_az, kappa):
    """Horizon elevation H (deg), blocker distance (m along the surface) and completeness flag for one site at map
    (x0, y0) metres. Each ray follows the true great circle leaving the site in map direction theta."""
    theta = np.arange(n_az) * (2 * np.pi / n_az)        # from map +x, counterclockwise
    d = step_schedule(terrain.levels[0].pixel, d_max, kappa)
    terrain.check_coverage(np.array([x0]), np.array([y0]), d)
    level = terrain.level_of(d)
    phi = d / R                                         # central angle to each sample
    p0, ex, ey = site_frame(x0, y0)
    t = np.cos(theta)[:, None] * ex + np.sin(theta)[:, None] * ey      # [n_az, 3]
    x, y = great_circle_xy(p0, t.T[:, :, None], np.cos(phi), np.sin(phi))   # [n_az, n_d]
    z = np.empty((n_az, d.size))
    for i, dem in enumerate(terrain.levels):           # each level samples its own stretch of every ray
        k = level == i
        rows, cols = dem.xy_to_rowcol(x[:, k], y[:, k])
        z[:, k] = bilinear(dem.height, cols, rows)
    row0, col0 = terrain.levels[0].xy_to_rowcol(x0, y0)
    z0 = float(bilinear(terrain.levels[0].height, col0, row0))
    if np.isnan(z0):
        raise ValueError(f"site at x {x0:.0f} m, y {y0:.0f} m is on a no-data pixel")
    r_obs = R + z0 + mast
    r_pt = R + z
    up = r_pt * np.cos(phi) - r_obs                     # height above the observer's level
    out = r_pt * np.sin(phi)                            # horizontal distance
    ratio = np.where(np.isnan(z), -np.inf, up / out)    # tan(angle); max ratio = max angle
    k = np.argmax(ratio, axis=1)
    H = np.degrees(np.arctan(ratio[np.arange(n_az), k]))
    complete = ~np.isnan(z[:, -1])                      # False if the ray left the DEM
    return H, d[k], complete
