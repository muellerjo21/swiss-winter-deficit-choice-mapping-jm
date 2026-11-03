"""Tests of the cost decomposition (rule cost_groups) and the cost-scope switch (price.cost_scope): the groups add up
to the system cost, every technology is in one group, the power plant fuel costs (electricity_fuel) are consistent,
and the national price attribute of the main pipeline is the one of the configured scope (total: all costs, the main
analysis; electricity: electricity costs only; electricity_fuel: plus the fuel costs of the power plants).

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


def test_power_fuel_table(power_fuel_cost):
    """Fuel cost = fuel consumed x unit cost; the part on electricity = fuel cost x electricity share in [0, 1]; the
    efficiency (electricity / fuel) of a plant that burns fuel is in (0, 1]."""
    t = power_fuel_cost
    assert np.allclose(t["fuel_cost"], t["fuel_gwh"] * t["unit_cost"], rtol=1e-12, atol=0)
    assert np.allclose(t["fuel_cost_electricity"], t["fuel_cost"] * t["electricity_share"], rtol=1e-12, atol=0)
    assert ((t["electricity_share"] >= 0) & (t["electricity_share"] <= 1)).all()
    assert (t["unit_cost"] >= 0).all()
    burning = t[t["fuel_gwh"] > 1]
    assert ((burning["efficiency"] > 0) & (burning["efficiency"] <= 1)).all()


def test_electricity_fuel_cost(cost_groups, power_fuel_cost):
    """electricity_fuel = electricity costs + the plants' fuel costs on electricity, between electricity and total."""
    fuel = power_fuel_cost.groupby("scenario_id")["fuel_cost_electricity"].sum().reindex(cost_groups.index, fill_value=0.0)
    assert np.allclose(cost_groups["cost_electricity_fuel"], cost_groups["cost_electricity"] + fuel, rtol=1e-12, atol=0)
    assert (cost_groups["cost_electricity"] <= cost_groups["cost_electricity_fuel"]).all()
    assert (cost_groups["cost_electricity_fuel"] <= cost_groups["cost_total"]).all()
