"""Attribute contributions of fig3/figA1 (src/make_graphics.group_contributions): for every group (Switzerland,
DE-CH, FR-CH) and scenario the contributions sum to the utility of the group, in the regional main analysis and in
the national aggregate.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

ATOL = 1e-12
GROUPS = ["national", "DE_CH", "FR_CH"]


@pytest.mark.parametrize("analysis", ["regional", "national"])
def test_contributions_sum_to_utility(request, analysis):
    contributions = request.getfixturevalue(f"contributions_{analysis}")
    rankings = request.getfixturevalue("rankings_regional" if analysis == "regional" else "rankings")
    if "scenario_id" in rankings.columns:  # rankings_regional is not indexed
        rankings = rankings.set_index("scenario_id")
    assert sorted(contributions["group"].unique()) == sorted(GROUPS)
    for group in GROUPS:
        c = contributions[contributions["group"] == group].set_index("scenario_id")
        assert set(c.index) == set(rankings.index)
        parts = c.drop(columns=["group", "total"])
        assert np.abs(parts.sum(axis=1) - c["total"]).max() < ATOL
        assert np.abs(c["total"] - rankings.loc[c.index, f"utility_{group}"]).max() < ATOL, group
