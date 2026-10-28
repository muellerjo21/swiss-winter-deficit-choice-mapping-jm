"""Unit tests of the credible intervals (src/intervals.py): HDI equals the equal-tailed interval for a symmetric
distribution, is shorter for a skewed one, contains the mode and is never wider than the equal-tailed interval.
The equality with arviz.hdi on the posterior samples is checked in the rule regional_utility (test_regional.py).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from intervals import credible_interval, credible_interval_label, credible_interval_tag, hdi  # noqa: E402

N = 200_000
RNG_SEED = 20251


@pytest.fixture(scope="module")
def symmetric():
    return np.random.default_rng(RNG_SEED).normal(0.0, 1.0, N)


@pytest.fixture(scope="module")
def skewed():
    return np.random.default_rng(RNG_SEED).gamma(2.0, 1.0, N)  # mode (k - 1) * theta = 1


def _width(interval):
    return interval[1] - interval[0]


@pytest.mark.parametrize("probability", [0.9, 0.94, 0.96])
def test_symmetric_hdi_equals_equal_tailed(symmetric, probability):
    h = credible_interval(symmetric, probability, "hdi")
    e = credible_interval(symmetric, probability, "equal_tailed")
    assert np.allclose(h, e, atol=0.02)  # sampling noise of the tails with N samples


@pytest.mark.parametrize("probability", [0.9, 0.94, 0.96])
def test_skewed_hdi_shorter_and_shifted(skewed, probability):
    h = credible_interval(skewed, probability, "hdi")
    e = credible_interval(skewed, probability, "equal_tailed")
    assert _width(h) < 0.97 * _width(e)
    assert h[0] < e[0] and h[1] < e[1]  # right-skewed: HDI shifted towards the mode


@pytest.mark.parametrize("probability", [0.5, 0.9, 0.96])
def test_hdi_contains_mode(skewed, probability):
    low, high = hdi(skewed, probability)
    assert low < 1.0 < high


@pytest.mark.parametrize("probability", [0.5, 0.9, 0.94, 0.96])
@pytest.mark.parametrize("distribution", ["symmetric", "skewed"])
def test_hdi_not_wider_than_equal_tailed(request, distribution, probability):
    x = request.getfixturevalue(distribution)
    # the equal-tailed interval interpolates between samples, so it may be narrower by at most one sample gap
    tolerance = np.diff(np.sort(x)).max()
    assert _width(hdi(x, probability)) <= _width(credible_interval(x, probability, "equal_tailed")) + tolerance


def test_hdi_mass_and_endpoints(skewed):
    low, high = hdi(skewed, 0.96)
    inside = ((skewed >= low) & (skewed <= high)).mean()
    assert 0.96 <= inside <= 0.96 + 2 / N
    assert low in skewed and high in skewed  # endpoints are samples (as arviz.hdi, method "nearest")


def test_tags_and_labels():
    assert credible_interval_tag(0.96, "hdi") == "hdi96"
    assert credible_interval_tag(0.94, "equal_tailed") == "eti94"
    assert credible_interval_label(0.96, "hdi") == "96% HDI"
    with pytest.raises(ValueError):
        credible_interval([1.0, 2.0], 0.96, "quantile")
