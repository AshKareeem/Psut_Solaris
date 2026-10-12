"""Fast horizon engine. YOUR WEEK-2 TASK, Ash.

Implement `horizon_profiles_fast` with Numba so that tests/test_fast.py passes.
Follow the study guide, section 3.4:
  1. precompute d, cos(phi), sin(phi) and cos(theta), sin(theta) once
  2. compare tangents instead of angles (one atan per ray)
  3. exact early exit using the tallest terrain z_max
  4. @njit(parallel=True) with prange over sites
It must give the same answer as horizon.reference.horizon_profile for every site.
"""


def horizon_profiles_fast(dem, pixel, cols, rows, mast, d_max, n_az=1440, kappa=0.001):
    """Horizon for many sites at once.

    dem         float32 [n, n] heights in metres
    cols, rows  1-D arrays of site positions (fractional grid indices), same order as the reference
    returns     H [sites, n_az] degrees, D [sites, n_az] metres, complete [sites, n_az] bool
    """
    raise NotImplementedError("Ash: implement with Numba (study guide section 3.4)")
