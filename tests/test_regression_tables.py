"""Regression of further tables against the frozen references in data/processed/: regional inputs (population and
ElCom reference values per region), pairwise choice probabilities (matrix, map regions, comparison of the two
aggregations) and the attribute contributions of fig3/figA1. Tolerances as in test_regression.py.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

EXACT_ATOL = 1e-9       # deterministic values (attributes, prices, contributions with posterior-mean coefficients)
POSTERIOR_ATOL = 0.005  # values from posterior draws (probabilities and their intervals), as UTILITY_ATOL


def _aligned(actual, expected, keys):
    assert list(actual.columns) == list(expected.columns)
    a, e = actual.set_index(keys).sort_index(), expected.set_index(keys).sort_index()
    assert list(a.index) == list(e.index)
    return a, e


def _max_abs_diff(a, e, columns):
    return float(np.nanmax(np.abs(a[columns].to_numpy(float) - e[columns].to_numpy(float))))


def test_population_by_region(population_by_region, reference_population_by_region):
    a, e = _aligned(population_by_region, reference_population_by_region, ["region"])
    assert (a["population"] == e["population"]).all()


def test_elcom_by_region(elcom_by_region, reference_elcom_by_region):
    a, e = _aligned(elcom_by_region, reference_elcom_by_region, ["region"])
    assert _max_abs_diff(a, e, ["total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh"]) < EXACT_ATOL
    assert (a[["n_rows", "n_municipalities"]] == e[["n_rows", "n_municipalities"]]).all().all()


def test_pairwise_matrix(pairwise_matrix, reference_pairwise_matrix_regional):
    a, e = _aligned(pairwise_matrix, reference_pairwise_matrix_regional, ["scenario_1", "scenario_2"])
    assert (a[["row", "column"]] == e[["row", "column"]]).all().all()  # same scenario order
    assert _max_abs_diff(a, e, ["p_mean", "p_low", "p_high", "p_mean_utility_aggregation"]) < POSTERIOR_ATOL


def test_pairwise_regions(pairwise_regions, reference_pairwise_regions_regional):
    a, e = _aligned(pairwise_regions, reference_pairwise_regions_regional, ["scenario_1", "scenario_2", "region"])
    assert _max_abs_diff(a, e, ["p_mean", "p_low", "p_high"]) < POSTERIOR_ATOL


def test_aggregation_comparison(aggregation_comparison_regional, reference_aggregation_comparison_regional):
    a, e = aggregation_comparison_regional, reference_aggregation_comparison_regional
    assert list(a.columns) == list(e.columns)
    keys = ["n_pairs", "max_pair_scenario_1", "max_pair_scenario_2"]
    assert a[keys].values.tolist() == e[keys].values.tolist()
    assert _max_abs_diff(a, e, ["max_abs_diff", "mean_abs_diff", "max_pair_p_mean",
                                "max_pair_p_mean_utility_aggregation"]) < POSTERIOR_ATOL


@pytest.mark.parametrize("analysis", ["regional", "national"])
def test_contributions(request, analysis):
    actual = request.getfixturevalue(f"contributions_{analysis}")
    expected = request.getfixturevalue(f"reference_contributions_{analysis}")
    a, e = _aligned(actual, expected, ["group", "scenario_id"])
    assert _max_abs_diff(a, e, list(a.columns)) < EXACT_ATOL
