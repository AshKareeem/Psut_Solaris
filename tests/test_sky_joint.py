"""Joint test between Step 1 (the horizon engine) and Step 2 (CE 2's Sun and Earth directions).

Study guide section 3.10: "put a fake Sun exactly behind your test cone and confirm the pipeline says hidden."

For sites from near the pole out to about 6 degrees, a cone is placed in several map directions. Step 2's geometry
(scripts/make_sky.py) computes the direction and height of the cone's tip from the site; the engine computes the
skyline. They must agree, and a fake Sun just below / above the tip must come out hidden / visible with the
team's Step 3 formula.
"""
import numpy as np
import pytest

from horizon.dem import PolarDEM, latlon_to_xy, xy_to_latlon
from horizon.reference import R, horizon_profile
from horizon.synthetic import cone, distance_grid
from horizon.terrain import single
from scripts.make_sky import az_el_theta, local_axes

SITES = [(-89.5, 0.0), (-89.5, 90.0), (-89.778601, -155.72556), (-85.0, 45.0), (-84.2, -120.0)]
BEARINGS = [0, 37, 90, 200, 300]   # map directions of the cone from the site, degrees
MASTS = [0.0, 10.0]
N, PIXEL, DIST, PEAK, BASE = 1201, 20.0, 6000.0, 300.0, 1500.0


@pytest.mark.parametrize("lat,lon", SITES)
@pytest.mark.parametrize("bearing", BEARINGS)
@pytest.mark.parametrize("mast", MASTS)
def test_sky_direction_and_height_match_the_engine(lat, lon, bearing, mast):
    xs, ys = latlon_to_xy(lat, lon)
    c = (N - 1) / 2
    dx, dy = DIST * np.cos(np.radians(bearing)), DIST * np.sin(np.radians(bearing))
    h = cone(distance_grid(N, PIXEL, c - dy / PIXEL, c + dx / PIXEL), peak=PEAK, base_radius=BASE)
    dem = PolarDEM(height=h.astype(np.float32), pixel=PIXEL, pole_row=c + ys / PIXEL, pole_col=c - xs / PIXEL)
    H, _, _ = horizon_profile(single(dem), xs, ys, mast=mast, d_max=11_000, n_az=1440, kappa=0.0005)

    # Step 2: direction and height of the cone tip, seen from the site (site at height 0 + mast)
    plat, plon = xy_to_latlon(xs + dx, ys + dy)
    up_s, east_s, north_s = local_axes(np.array([lat]), np.array([lon]))
    up_p, _, _ = local_axes(np.array([plat]), np.array([plon]))
    v = (up_p[0] * (R + PEAK) - up_s[0] * (R + mast))[None, None, :]
    th, el = az_el_theta(v, up_s, east_s, north_s, np.array([lon]))
    th, el = float(th[0, 0]), float(el[0, 0])

    j = int(np.argmax(H))
    assert abs((th - j * 0.25 + 180) % 360 - 180) < 0.05, "Step 2 direction disagrees with the engine"
    assert abs(el - H[j]) < 0.05, "Step 2 height disagrees with the engine"

    # Fake Sun behind the cone (team Step 3 formula, Sun radius 0.27 deg)
    H_at = np.interp(th, np.arange(1441) * 0.25, np.append(H, H[0]))
    s = lambda sun_el: float(np.clip((sun_el - H_at + 0.27) / 0.54, 0, 1))
    assert s(el - 0.5) == 0.0, "Sun just behind the cone should be hidden"
    assert s(el + 0.5) == 1.0, "Sun just above the cone should be fully visible"
