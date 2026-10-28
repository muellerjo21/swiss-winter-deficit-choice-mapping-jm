"""Checks of the regional analysis (src/regional.py): weights, merged regions, no NaN, and the artificial
constellation that must reproduce the national result. The checks are computed in the rule regional_utility
(the test environment has no access to the choice model); regional results get frozen references only after
approval.

Pytest fixtures are provided from within the test runner.
"""
import pytest

CHECKS = ["weights sum to 1", "negative weights", "NaN in regional attributes", "NaN in shares of a region without capacity",
          "population total = STATPOP total", "artificial: utility = national DE-CH",
          "artificial: P(rank 1) = national DE-CH", "artificial: ranks = national DE-CH", "HDI = arviz.hdi"]


@pytest.mark.parametrize("name", CHECKS)
def test_regional_check(regional_checks, name):
    row = regional_checks.set_index("check").loc[name]
    assert row["value"] <= row["tolerance"], f"{name}: {row['value']}"


def test_merged_regions_summed(regional_checks):
    merged = regional_checks[regional_checks["check"].str.contains(r"= sum of")]
    assert len(merged) == 6  # area and population of AI_AR, BL_BS, NW_OW
    assert merged["passed"].all(), merged[~merged["passed"]]


def test_regional_attributes_complete(regional_attributes):
    assert regional_attributes["region"].nunique() == 23
    assert regional_attributes.groupby("scenario_id")["region"].nunique().eq(23).all()
    assert not regional_attributes.drop(columns=["language", "mellot_cost_change_pct"]).isna().any().any()
