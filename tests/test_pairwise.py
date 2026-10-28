"""Tests of the pairwise choice probabilities of the regional analysis (rule pairwise_regional, src/pairwise.py)
and of the region geometries of the maps (rule choice_maps, src/maps.py). The checks that need the posterior
samples (weights, single-region calculation) are computed in the rules; the test environment reads the CSVs.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

ATOL = 1e-12

CHECKS = ["weights sum to 1", "p(A>B) + p(B>A) = 1", "diagonal = 0.5", "probabilities in [0, 1]",
          "interval contains the mean", "single region = region table",
          "national mean = weighted mean of regional means"]


@pytest.mark.parametrize("name", CHECKS)
def test_pairwise_check(pairwise_checks, name):
    row = pairwise_checks.set_index("check").loc[name]
    assert row["value"] <= row["tolerance"], f"{name}: {row['value']}"


def test_matrix_complete(pairwise_matrix):
    n = pairwise_matrix["scenario_1"].nunique()
    assert n == 12 and len(pairwise_matrix) == n * n
    assert not pairwise_matrix.duplicated(["scenario_1", "scenario_2"]).any()


def test_matrix_complementary(pairwise_matrix):
    m = pairwise_matrix.set_index(["scenario_1", "scenario_2"])["p_mean"]
    swapped = m.reindex([(b, a) for a, b in m.index]).to_numpy()
    assert np.abs(m.to_numpy() + swapped - 1).max() < ATOL


def test_matrix_diagonal(pairwise_matrix):
    diag = pairwise_matrix[pairwise_matrix["scenario_1"] == pairwise_matrix["scenario_2"]]
    assert (diag[["p_mean", "p_low", "p_high", "p_mean_utility_aggregation"]] == 0.5).all().all()


def test_probabilities_in_unit_interval(pairwise_matrix, pairwise_regions):
    for table, columns in [(pairwise_matrix, ["p_mean", "p_low", "p_high", "p_mean_utility_aggregation"]),
                           (pairwise_regions, ["p_mean", "p_low", "p_high"])]:
        values = table[columns].to_numpy()
        assert ((values >= 0) & (values <= 1)).all()
        assert (table["p_low"] <= table["p_mean"] + ATOL).all() and (table["p_mean"] <= table["p_high"] + ATOL).all()


def test_map_tables_match_regions(pairwise_map_tables, pairwise_regions):
    """One table per map pair, each the subset of the region table; 22 regions (TI excluded)."""
    for table in pairwise_map_tables:
        a, b = table["scenario_1"].iloc[0], table["scenario_2"].iloc[0]
        subset = pairwise_regions[(pairwise_regions["scenario_1"] == a) & (pairwise_regions["scenario_2"] == b)]
        assert table.reset_index(drop=True).equals(subset.reset_index(drop=True))
        assert table["region"].nunique() == 22 and "TI" not in set(table["region"])


def test_every_region_has_one_geometry(geometry_checks):
    analysis = geometry_checks[geometry_checks["in_analysis"]]
    assert len(analysis) == 23
    assert (analysis["n_geometries"] == 1).all(), analysis[analysis["n_geometries"] != 1]
    assert geometry_checks["in_analysis"].all(), geometry_checks[~geometry_checks["in_analysis"]]
    assert geometry_checks["passed"].all(), geometry_checks[~geometry_checks["passed"]]
