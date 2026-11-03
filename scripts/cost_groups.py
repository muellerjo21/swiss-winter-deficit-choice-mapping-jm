"""Decomposition of the Swiss system cost C_s into the cost groups of price.cost_groups (electricity, other) per
technology and scenario, the simulated national price p_sim with all costs and with the electricity costs only, and
the electricity produced by power plants whose fuel costs are in the group other (price.fuel_power_techs), and the
fuel costs of these plants (load_data.load_power_fuel_cost) for the cost scope electricity_fuel, and for the cost scope
energy the final energy demand, p_sim with all costs over it and the import shares over it."""
import json
import sys
from pathlib import Path

import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import FOREIGN_CODES
from load_data import (aggregate_national, import_quantities, load_power_fuel_cost, load_scenario_cost_by_technology,
                       load_scenario_demand, load_scenario_final_energy, scope_reference, simulated_price)


def fuel_power_gwh(nc_path: str, techs: list) -> float:
    """Annual electricity production (GWh) of the given technologies at the Swiss locations."""
    ds = xr.open_dataset(nc_path)
    prod = ds.coords["loc_tech_carriers_prod"].values
    sel = [c for c in prod if c.split("::")[0] not in FOREIGN_CODES and c.split("::")[1] in techs
           and c.split("::")[2] == "electricity"]
    out = float(ds["carrier_prod"].sel(loc_tech_carriers_prod=sel).sum()) if sel else 0.0
    ds.close()
    return out


def cost_groups(paths_to_nc, scenario_ids, groups, fuel_power_techs, power_fuel, energy_reference, fuel_techs,
                diesel_techs, cost_scale, path_to_elcom, path_to_eur_chf, path_to_groups, path_to_technologies,
                path_to_power_fuel, path_to_final_energy):
    elcom = json.loads(Path(path_to_elcom).read_text())
    ref = {k: elcom[k] for k in ("total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh")}
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    rows, techs, fuels, energy = [], [], [], []
    energy_ref = scope_reference(ref, "energy", energy_reference)
    for s, nc in zip(scenario_ids, paths_to_nc):
        by_tech = load_scenario_cost_by_technology(nc, groups).assign(scenario_id=s)
        techs.append(by_tech[["scenario_id", "tech", "group", "cost"]])
        cost = by_tech.groupby("group")["cost"].sum()
        demand = aggregate_national(load_scenario_demand(nc), "demand_gwh")
        total = float(by_tech["cost"].sum())
        fuel = load_power_fuel_cost(nc, **power_fuel).assign(scenario_id=s)
        fuels.append(fuel)
        electricity_fuel = float(cost.get("electricity", 0.0)) + float(fuel["fuel_cost_electricity"].sum())
        rows.append({"scenario_id": s, "cost_total": total, **{f"cost_{g}": float(cost.get(g, 0.0)) for g in groups},
                     "share_electricity": float(cost.get("electricity", 0.0)) / total, "demand_gwh": demand,
                     "cost_scale_factor": cost_scale,
                     "p_sim_total_rp_kwh": simulated_price(cost_scale * total, demand, ref, eur_to_chf),
                     "p_sim_electricity_rp_kwh": simulated_price(cost_scale * float(cost.get("electricity", 0.0)), demand,
                                                                 ref, eur_to_chf),
                     "fuel_power_gwh": fuel_power_gwh(nc, fuel_power_techs), "cost_electricity_fuel": electricity_fuel,
                     "p_sim_electricity_fuel_rp_kwh": simulated_price(cost_scale * electricity_fuel, demand, ref,
                                                                      eur_to_chf)})
        final = load_scenario_final_energy(nc)
        p_sim = simulated_price(cost_scale * total, final["final_energy"], energy_ref, eur_to_chf)
        imports = import_quantities(nc, fuel_techs, diesel_techs, "final_energy")
        energy.append({"scenario_id": s, **{f"{k}_gwh": v for k, v in final.items()}, "demand_gwh": demand,
                       "cost_total": total, "cost_scale_factor": cost_scale, "p_ref_rp_kwh": energy_ref["total_rp_kwh"],
                       "p_sim_energy_rp_kwh": p_sim,
                       "price_change_energy": (p_sim - energy_ref["total_rp_kwh"]) / energy_ref["total_rp_kwh"],
                       **{k: v for k, v in imports.items() if k.startswith("import_share_")}})
    pd.DataFrame(rows).to_csv(path_to_groups, index=False)
    pd.DataFrame(energy).to_csv(path_to_final_energy, index=False)
    pd.concat(techs, ignore_index=True).to_csv(path_to_technologies, index=False)
    columns = ["scenario_id", *[c for c in fuels[0].columns if c != "scenario_id"]]
    pd.concat(fuels, ignore_index=True)[columns].to_csv(path_to_power_fuel, index=False)


if __name__ == "__main__":
    p = snakemake.params
    cost_groups(list(snakemake.input.nc), p.scenario_ids, p.cost_groups, p.fuel_power_techs, p.power_fuel,
                p.energy_reference, p.fuel_techs, p.diesel_techs, p.cost_scale, snakemake.input.elcom,
                snakemake.input.eur_chf, snakemake.output.groups, snakemake.output.technologies,
                snakemake.output.power_fuel, snakemake.output.final_energy)
