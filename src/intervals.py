"""Credible intervals from posterior samples (numpy only, so that every conda environment and the tests can use
it). Type and level are set in config/default.yaml (utility.interval_type, utility.credible_interval).

- hdi: highest density interval = shortest interval that contains the given probability mass of the samples.
  Same algorithm as arviz.hdi (method "nearest"): sort the samples, take the narrowest window of
  floor(probability * n) + 1 consecutive samples. The pipeline checks the equality with arviz.hdi
  (scripts/regional_utility.py, check "HDI = arviz.hdi").
- equal_tailed: (1-p)/2 and 1-(1-p)/2 quantiles (linear interpolation).
"""
import numpy as np

INTERVAL_TYPES = ("hdi", "equal_tailed")


def _check(probability: float, interval_type: str) -> None:
    if not 0 < probability <= 1:
        raise ValueError(f"credible interval probability must be in (0, 1], got {probability}")
    if interval_type not in INTERVAL_TYPES:
        raise ValueError(f"interval_type must be one of {INTERVAL_TYPES}, got {interval_type!r}")


def equal_tailed_quantiles(probability: float) -> tuple[float, float]:
    """Lower and upper quantile of the equal-tailed interval: (1-p)/2 and 1-(1-p)/2. Rounded to 12 decimals,
    because e.g. (1-0.94)/2 is 0.030000000000000027 in floating point."""
    tail = (1 - probability) / 2
    return round(tail, 12), round(1 - tail, 12)


def hdi(samples, probability: float) -> tuple[float, float]:
    """Highest density interval of 1-d samples (as arviz.hdi, method "nearest")."""
    x = np.sort(np.asarray(samples, dtype=float).ravel())
    n = len(x)
    inc = int(np.floor(probability * n))
    widths = x[inc:] - x[:n - inc]
    if len(widths) == 0:
        raise ValueError("too few samples for the interval")
    i = int(np.argmin(widths))
    return float(x[i]), float(x[i + inc])


def credible_interval(samples, probability: float, interval_type: str = "hdi") -> tuple[float, float]:
    """(low, high) of the credible interval of 1-d posterior samples."""
    _check(probability, interval_type)
    if interval_type == "hdi":
        return hdi(samples, probability)
    low, high = equal_tailed_quantiles(probability)
    q = np.quantile(np.asarray(samples, dtype=float).ravel(), [low, high])
    return float(q[0]), float(q[1])


def credible_interval_tag(probability: float, interval_type: str = "hdi") -> str:
    """Tag of the interval in column and file names: 'hdi96' for a 96 % HDI, 'eti94' for a 94 % equal-tailed
    interval (utility_<group>_<tag>_low/high)."""
    _check(probability, interval_type)
    return f"{'hdi' if interval_type == 'hdi' else 'eti'}{probability * 100:g}"


def credible_interval_label(probability: float, interval_type: str = "hdi") -> str:
    """Text for figure captions, e.g. '96% HDI' or '94% equal-tailed credible interval'."""
    _check(probability, interval_type)
    kind = "HDI" if interval_type == "hdi" else "equal-tailed credible interval"
    return f"{probability * 100:g}% {kind}"
