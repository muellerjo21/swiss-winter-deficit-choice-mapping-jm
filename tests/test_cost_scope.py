"""Tests of the cost decomposition (rule cost_groups) and the cost-scope switch (price.cost_scope): the groups add up
to the system cost, every technology is in one group, and the national price attribute of the main pipeline is the
one of the configured scope (total: all costs, the main analysis; electricity: electricity costs only).

Pytest fixtures are provided from within the test runner.
"""
import numpy as np

CONSISTENCY_ATOL = 1e-12


def test_groups_add_up_to_total(cost_groups):
    assert np.allclose(cost_groups["cost_electricity"] + cost_groups["cost_other"], cost_groups["cost_total"],
                       rtol=1e-12, atol=0)
    assert ((cost_groups["share_electricity"] >= 0) & (cost_groups["share_electricity"] <= 1)).all()


def test_every_technology_in_one_group(cost_by_technology, cost_groups):
    assert set(cost_by_technology["group"]) <= {"electricity", "other"}
    assert not cost_by_technology.duplicated(["scenario_id", "tech"]).any()
    per_scenario = cost_by_technology.groupby("scenario_id")["cost"].sum()
    assert np.allclose(per_scenario.loc[cost_groups.index], cost_groups["cost_total"], rtol=1e-12, atol=0)


def test_main_price_uses_cost_scope(attributes, cost_groups, cost_scope, elcom_national):
    """price_change of the national attributes = p_sim of the configured cost scope relative to the ElCom price."""
    p_sim = cost_groups[f"p_sim_{cost_scope}_rp_kwh"]
    expected = (p_sim - elcom_national["total_rp_kwh"]) / elcom_national["total_rp_kwh"]
    assert np.abs(attributes.loc[cost_groups.index, "price_change"] - expected).max() < CONSISTENCY_ATOL


def test_electricity_price_below_total(cost_groups):
    """Without the other costs the simulated price can only fall (all group costs are non-negative)."""
    assert (cost_groups["cost_other"] >= 0).all()
    assert (cost_groups["p_sim_electricity_rp_kwh"] <= cost_groups["p_sim_total_rp_kwh"]).all()
