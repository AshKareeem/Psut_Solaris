import numpy as np

from horizon.dem import latlon_to_xy, xy_to_latlon
from horizon.reference import R, great_circle_xy, site_frame


def walk(x0, y0, theta_deg, d):
    p0, ex, ey = site_frame(x0, y0)
    th = np.radians(theta_deg)
    t = np.cos(th) * ex + np.sin(th) * ey
    return great_circle_xy(p0, t, np.cos(d / R), np.sin(d / R))


def test_from_the_pole_map_radius_is_2R_tan_half_angle():
    for theta in (0.0, 90.0, 217.5):
        x, y = walk(0.0, 0.0, theta, 250_000.0)
        assert abs(np.hypot(x, y) - 2 * R * np.tan(250_000.0 / (2 * R))) < 1e-6
        assert abs(np.degrees(np.arctan2(y, x)) % 360 - theta) < 1e-9


def test_rays_leave_every_site_in_map_direction_theta():
    for lat, lon in ((-89.9, 30.0), (-87.0, -120.0), (-84.0, 200.0)):
        x0, y0 = latlon_to_xy(lat, lon)
        for theta in (0.0, 45.0, 90.0, 300.0):
            x, y = walk(x0, y0, theta, 1.0)            # 1 m out: the map is conformal, so the direction is theta
            off = (np.degrees(np.arctan2(y - y0, x - x0)) - theta + 180) % 360 - 180
            assert abs(off) < 1e-4


def test_samples_match_the_great_circle_destination_formula():
    """Independent spherical trigonometry: destination at distance d on initial bearing A (clockwise from north).
    Map direction theta = beta - A, where beta = 90 - lon is local north on the map."""
    for lat, lon in ((-89.78, -155.7), (-87.0, 45.0), (-84.0, -100.0)):
        x0, y0 = latlon_to_xy(lat, lon)
        for theta in (10.0, 90.0, 200.0, 333.0):
            for d in (40_000.0, 250_000.0):
                bearing = np.radians(90.0 - lon - theta)
                la, lo, delta = np.radians(lat), np.radians(lon), d / R
                la2 = np.arcsin(np.sin(la) * np.cos(delta) + np.cos(la) * np.sin(delta) * np.cos(bearing))
                lo2 = lo + np.arctan2(np.sin(bearing) * np.sin(delta) * np.cos(la),
                                      np.cos(delta) - np.sin(la) * np.sin(la2))
                x_true, y_true = latlon_to_xy(np.degrees(la2), np.degrees(lo2))
                x, y = walk(x0, y0, theta, d)
                assert np.hypot(x - x_true, y - y_true) < 1e-3   # within 1 mm


def test_map_position_round_trips_through_lat_lon():
    x, y = walk(*latlon_to_xy(-85.5, 29.0), 123.0, 180_000.0)
    lat, lon = xy_to_latlon(x, y)
    assert np.allclose(latlon_to_xy(lat, lon), (x, y), atol=1e-6)
