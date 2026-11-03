"""Sensitivity of the regional main analysis to the Calliope system cost: all system costs C_s multiplied by a common
factor (e.g. a price-year conversion); rank and P(rank 1) per factor and the factors at which rank 1 changes
(src/regional.py)."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS
from load_data import load_scenario_cost_and_demand
from regional import (load_regional_model, population_weights, region_coefficients, regional_cost_scale_curve,
                      regional_cost_scale_switches, regional_rankings, regional_utilities)
from sensitivity import reference_price_grid


def sweep(path_to_attributes, path_to_population, path_to_elcom, path_to_eur_chf, paths_to_nc, scenario_ids,
          path_to_choice_model, exclude, coefficient_overrides, factors, search, tolerance, check_delta, mobile_share, credible_interval,
          interval_type, path_to_curve, path_to_switches):
    attributes = pd.read_csv(path_to_attributes)
    population = pd.read_csv(path_to_population).set_index("region")["population"]
    elcom = pd.read_csv(path_to_elcom).set_index("region")
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    cost_and_demand = {s: load_scenario_cost_and_demand(p) for s, p in zip(scenario_ids, paths_to_nc)}  # unscaled
    model = load_regional_model(path_to_choice_model, mobile_share, LANGUAGE_REGION_WEIGHTS)
    weights = population_weights(population, exclude)
    coefficients = region_coefficients(population.index, coefficient_overrides)

    def rank_at(a):
        u, s, _, _ = regional_utilities(a, weights, coefficients, **model)
        return regional_rankings(a, u, s, credible_interval, interval_type)

    def leader_at(a, tag):
        u, _, _, _ = regional_utilities(a, weights, coefficients, **model, with_samples=False)
        return u.set_index("scenario_id")[f"utility_{tag}"].idxmax()

    regional_cost_scale_curve(attributes, cost_and_demand, elcom, eur_to_chf, factors, rank_at).to_csv(
        path_to_curve, index=False)
    grid = reference_price_grid(search["start"], search["stop"], search["step"])
    regional_cost_scale_switches(attributes, cost_and_demand, elcom, eur_to_chf, grid, leader_at, tolerance,
                                 check_delta).to_csv(path_to_switches, index=False)


if __name__ == "__main__":
    p = snakemake.params
    sweep(snakemake.input.attributes, snakemake.input.population, snakemake.input.elcom, snakemake.input.eur_chf,
          list(snakemake.input.nc), p.scenario_ids, snakemake.input.choice_model, p.exclude,
          p.coefficient_overrides, p.factors, p.search,
          p.tolerance, p.check_delta, p.mobile_share, p.credible_interval, p.interval_type, snakemake.output.curve,
          snakemake.output.switches)
