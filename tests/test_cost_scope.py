"""Tests of the cost decomposition (rule cost_groups) and the cost-scope switch (price.cost_scope): the groups add up
to the system cost, every technology is in one group, the power plant fuel costs (electricity_fuel) are consistent,
and the national price attribute of the main pipeline is the one of the configured scope (total: all costs, the main
analysis; electricity: electricity costs only; electricity_fuel: plus the fuel costs of the power plants; energy: all
costs over the final energy demand, with its own reference price), and the import shares follow imports.denominator.

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


def test_main_price_uses_cost_scope(attributes, cost_groups, final_energy, cost_scope, elcom_national):
    """price_change of the national attributes = p_sim of the configured cost scope relative to its reference price."""
    if cost_scope == "energy":
        expected = final_energy.loc[cost_groups.index, "price_change_energy"]
    else:
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


def test_final_energy(final_energy):
    """Final energy = electricity + heat + transport, all positive; above the electricity demand demand_elec."""
    t = final_energy
    assert np.allclose(t["final_energy_gwh"], t["electricity_gwh"] + t["heat_gwh"] + t["transport_gwh"], rtol=1e-12, atol=0)
    assert (t[["electricity_gwh", "heat_gwh", "transport_gwh"]] > 0).all().all()


def test_energy_reference_price(final_energy, energy_reference, elcom_national):
    """p_ref of the energy scope = price.energy_reference_ct_per_kwh, or the ElCom electricity reference if null."""
    expected = elcom_national["total_rp_kwh"] if energy_reference is None else float(energy_reference)
    assert (final_energy["p_ref_rp_kwh"] == expected).all()


def test_import_shares_follow_denominator(import_shares, final_energy, import_denominator):
    """The import shares of the pipeline use imports.denominator; the import quantities are the same with both
    denominators (shares x denominator)."""
    shares = import_shares.set_index("scenario_id").loc[final_energy.index]
    assert ("final_energy_gwh" in shares.columns) == (import_denominator == "final_energy")
    base = shares["final_energy_gwh"] if import_denominator == "final_energy" else shares["consumption_gwh"]
    for name in ["electricity", "electricity_fuels", "electricity_fuels_diesel"]:
        quantity = shares[f"import_share_{name}_unclipped"] * base
        assert np.allclose(quantity, final_energy[f"import_share_{name}_unclipped"] * final_energy["final_energy_gwh"],
                           rtol=1e-12, atol=0), name
        assert np.allclose(shares[f"import_share_{name}"], shares[f"import_share_{name}_unclipped"].clip(0, 1),
                           rtol=0, atol=0), name
