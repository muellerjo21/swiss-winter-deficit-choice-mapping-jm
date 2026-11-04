"""Regional analysis for one weather year (sensitivity.weather_years): national and regional attributes of every scenario
with a result file for that year, rankings with credible interval and P(rank 1) over these scenarios and over the
scenarios available in all weather years. Same functions and settings as the main analysis (scenario_attributes,
regional_attributes, regional_utility); the reference prices (ElCom 2025, or price.energy_reference_ct_per_kwh with
cost_scope energy), population and EUR/CHF rate are the same in every year."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS
from load_data import (compute_all_attributes, import_quantities, load_canton_area, scope_reference,
                       scope_reference_table)
from regional import (load_regional_model, population_weights, region_coefficients, regional_attribute_table,
                      regional_rankings, regional_utilities)


def national_attributes(nc_by_scenario, area, elcom_ref, eur_to_chf, land_definition, cost_options):
    """As scenario_attributes + compute_attributes: one row per scenario, sorted by scenario_id."""
    rows = []
    for s, nc in nc_by_scenario.items():
        row = compute_all_attributes(nc, area, elcom_ref, eur_to_chf, land_definition, **cost_options)
        row["scenario_id"] = s
        rows.append(row)
    return pd.DataFrame(rows).sort_values("scenario_id")


def rankings(attributes, weights, coefficients, model, credible_interval, interval_type):
    u, samples, _, _ = regional_utilities(attributes, weights, coefficients, **model)
    return regional_rankings(attributes, u, samples, credible_interval, interval_type)


def weather_year(p, inp, out):
    nc_by_scenario = dict(zip(p.scenario_ids, inp.nc))
    area = load_canton_area(inp.canton_area)
    eur_to_chf = json.loads(Path(inp.eur_chf).read_text())["eur_to_chf"]
    elcom = json.loads(Path(inp.elcom_national).read_text())
    elcom_ref = scope_reference({k: elcom[k] for k in ("total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh")},
                                p.cost_scope, p.energy_reference)
    cost_options = dict(cost_scale=p.cost_scale, cost_scope=p.cost_scope, cost_groups=p.cost_groups,
                        power_fuel=p.power_fuel)
    national = national_attributes(nc_by_scenario, area, elcom_ref, eur_to_chf, p.land_definition, cost_options)
    national.assign(weather_year=p.year).to_csv(out.national, index=False)
    import_share = None
    if p.import_definition != "electricity":
        import_share = {s: import_quantities(nc, p.fuel_techs, p.diesel_techs, p.import_denominator)[
            f"import_share_{p.import_definition}"] for s, nc in nc_by_scenario.items()}
    price_reference = scope_reference_table(pd.read_csv(inp.elcom_regional).set_index("region"), p.cost_scope,
                                            p.energy_reference)
    attributes = regional_attribute_table(nc_by_scenario, area, national.set_index("scenario_id"), price_reference,
                                          eur_to_chf, cost_options, import_share)
    attributes.assign(weather_year=p.year).to_csv(out.attributes, index=False)

    population = pd.read_csv(inp.population).set_index("region")["population"]
    weights = population_weights(population, p.exclude)
    coefficients = region_coefficients(population.index, p.coefficient_overrides)
    model = load_regional_model(inp.choice_model, p.mobile_share, LANGUAGE_REGION_WEIGHTS)
    for scenarios, path in [(p.scenario_ids, out.rankings), (p.common_scenarios, out.rankings_common)]:
        a = attributes[attributes["scenario_id"].isin(scenarios)]
        rankings(a, weights, coefficients, model, p.credible_interval, p.interval_type).assign(
            weather_year=p.year, n_scenarios=len(scenarios)).to_csv(path, index=False)


if __name__ == "__main__":
    weather_year(snakemake.params, snakemake.input, snakemake.output)
