import numpy as np
import pytest

from scripts.validate_pgda import agreement


def test_agreement_in_percentage_points():
    nasa = np.array([0.0, 0.2, 0.5, 0.8])
    r, mean, within = agreement(nasa + np.array([0.05, 0.05, 0.05, 0.25]), nasa)
    assert r == pytest.approx(np.corrcoef(nasa + [0.05, 0.05, 0.05, 0.25], nasa)[0, 1])
    assert mean == pytest.approx(10.0)  # (5 + 5 + 5 + 25) / 4 points
    assert within == 0.75               # the 25-point miss is outside 10 points
