"""Regressionstest: Pipeline-Ergebnisse in build/ gegen die eingefrorenen, validierten
Referenzen in data/processed/.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

ATTRIBUTE_ATOL = 1e-9   # Attribute sind deterministisch (gepinnter EUR/CHF-Kurs) -> praktisch exakt
UTILITY_ATOL = 0.005    # Utility, CI und P(Rang 1)


def _max_abs_diff(actual, expected, columns):
    return np.nanmax(np.abs(actual.loc[expected.index, columns].to_numpy(float)
                            - expected[columns].to_numpy(float)))


def test_same_scenarios(attributes, reference_attributes, rankings, reference_rankings):
    assert set(attributes.index) == set(reference_attributes.index)
    assert set(rankings.index) == set(reference_rankings.index)


def test_attribute_columns(attributes, reference_attributes):
    assert set(attributes.columns) == set(reference_attributes.columns)


@pytest.mark.parametrize("column", [
    "relative_land", "import_share", "ownership_commercial", "ownership_community", "ownership_public",
    "source_wind", "source_gas", "source_biomass", "source_coal", "source_nuclear",
    "transmission_change", "price_change", "mellot_cost_change_pct",
])
def test_attribute_values(attributes, reference_attributes, column):
    assert _max_abs_diff(attributes, reference_attributes, [column]) < ATTRIBUTE_ATOL


def test_rankings_columns(rankings, reference_rankings):
    assert list(rankings.columns) == list(reference_rankings.columns)


def test_rankings_row_order(rankings, reference_rankings):
    assert list(rankings.index) == list(reference_rankings.index)


@pytest.mark.parametrize("tag", ["DE_CH", "FR_CH", "national"])
def test_utility_and_ci(rankings, reference_rankings, tag):
    cols = [f"utility_{tag}", f"utility_{tag}_ci94_low", f"utility_{tag}_ci94_high"]
    assert _max_abs_diff(rankings, reference_rankings, cols) < UTILITY_ATOL


@pytest.mark.parametrize("tag", ["DE_CH", "FR_CH", "national"])
def test_p_rank1(rankings, reference_rankings, tag):
    assert _max_abs_diff(rankings, reference_rankings, [f"p_rank1_{tag}"]) < UTILITY_ATOL


@pytest.mark.parametrize("column", [
    "rank_DE_CH", "rank_FR_CH", "rank_national", "rank_mellot_cost", "rank_diff_national_vs_mellot",
])
def test_ranks_identical(rankings, reference_rankings, column):
    actual = rankings.loc[reference_rankings.index, column]
    expected = reference_rankings[column]
    assert ((actual == expected) | (actual.isna() & expected.isna())).all()
