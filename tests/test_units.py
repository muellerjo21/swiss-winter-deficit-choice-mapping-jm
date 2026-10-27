"""Coefficients in real units: beta_real = beta / sigma, and the utility with raw attributes and real-unit
coefficients equals the utility with scaled attributes and model coefficients.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

EQUIVALENCE_ATOL = 1e-12


def test_beta_real_is_beta_over_sigma(beta_real_units):
    t = beta_real_units
    assert np.allclose(t["beta_real"], t["beta_mean"] / t["sigma"], rtol=0, atol=EQUIVALENCE_ATOL)
    assert np.allclose(t["gamma_real"], t["gamma_mean"] / t["sigma"], rtol=0, atol=EQUIVALENCE_ATOL)
    assert (t["sigma"] > 0).all()


@pytest.mark.parametrize("region", ["DE-CH", "FR-CH"])
def test_scaled_and_real_units_give_same_utility(beta_real_units, attributes, rankings, region):
    t = beta_real_units[beta_real_units["region"] == region].set_index("attribute")
    s = t["mobile_share"].iloc[0]
    term_of_column = dict(zip(t["scenario_column"], t.index))  # from ATTRIBUTE_COLUMN_TO_MODEL_TERM
    z = attributes[list(term_of_column)].rename(columns=term_of_column)
    u_scaled = sum(z[k] / t.loc[k, "sigma"] * (t.loc[k, "beta_mean"] + s * t.loc[k, "gamma_mean"]) for k in z.columns)
    u_real = sum(z[k] * (t.loc[k, "beta_real"] + s * t.loc[k, "gamma_real"]) for k in z.columns)
    assert np.abs(u_scaled - u_real).max() < EQUIVALENCE_ATOL
    assert np.abs(u_real - rankings.loc[u_real.index, f"utility_{region.replace('-', '_')}"]).max() < EQUIVALENCE_ATOL
