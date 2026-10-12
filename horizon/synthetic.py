"""Synthetic terrains with known answers, for tests and demos."""
import numpy as np


def distance_grid(n, pixel, row, col):
    """Distance in metres from (row, col) to every pixel of an n x n grid."""
    rr, cc = np.mgrid[0:n, 0:n]
    return np.hypot((rr - row) * pixel, (cc - col) * pixel)


def cone(r, peak, base_radius):
    """Cone of height `peak` falling to 0 at `base_radius`."""
    return np.maximum(0.0, peak * (1 - r / base_radius))


def ring(r, peak, radius, half_width):
    """Circular ridge of height `peak` at `radius`, triangular cross-section."""
    return np.maximum(0.0, peak * (1 - np.abs(r - radius) / half_width))


def bowl_crater(r, radius, depth, rim):
    """Bowl `depth` deep below its rim, rim `rim` high, rim falling off outside."""
    inside = rim - depth * (1 - (r / radius) ** 2)
    outside = rim * np.exp(-(r - radius) / (0.3 * radius))
    return np.where(r < radius, inside, outside)
