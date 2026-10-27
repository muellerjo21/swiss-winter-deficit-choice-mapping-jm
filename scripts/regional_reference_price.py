"""Regional reference-price sweep: common additive shift of all regional reference prices; curve of rank and
P(rank 1) per group and the shifts at which rank 1 changes (src/regional.py)."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_LANGUAGE, LANGUAGE_REGION_WEIGHTS
from load_data import load_scenario_cost_and_demand
from regional import (load_regional_model, population_weights, regional_price_curve, regional_rank1_switches,
                      regional_rankings, regional_utilities)
from sensitivity import reference_price_grid


def sweep(path_to_attributes, path_to_population, path_to_elcom, path_to_eur_chf, paths_to_nc, scenario_ids,
          path_to_choice_model, exclude, shift, tolerance, check_delta, mobile_share, credible_interval,
          path_to_curve, path_to_switches):
    attributes = pd.read_csv(path_to_attributes)
    population = pd.read_csv(path_to_population).set_index("region")["population"]
    elcom = pd.read_csv(path_to_elcom).set_index("region")
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    cost_and_demand = {s: load_scenario_cost_and_demand(p) for s, p in zip(scenario_ids, paths_to_nc)}
    model = load_regional_model(path_to_choice_model, mobile_share, LANGUAGE_REGION_WEIGHTS)
    weights = population_weights(population, exclude)
    coefficients = {r: CANTON_LANGUAGE.get(r) for r in population.index}

    def rank_at(a):
        u, s, _, _ = regional_utilities(a, weights, coefficients, **model)
        return regional_rankings(a, u, s, credible_interval)

    def leader_at(a, tag):
        u, _, _, _ = regional_utilities(a, weights, coefficients, **model, with_samples=False)
        return u.set_index("scenario_id")[f"utility_{tag}"].idxmax()

    grid = reference_price_grid(shift["start"], shift["stop"], shift["step"])
    curve = regional_price_curve(attributes, cost_and_demand, elcom, eur_to_chf, grid, rank_at)
    curve.to_csv(path_to_curve, index=False)
    regional_rank1_switches(attributes, cost_and_demand, elcom, eur_to_chf, curve, leader_at, tolerance,
                            check_delta).to_csv(path_to_switches, index=False)


if __name__ == "__main__":
    p = snakemake.params
    sweep(snakemake.input.attributes, snakemake.input.population, snakemake.input.elcom, snakemake.input.eur_chf,
          list(snakemake.input.nc), p.scenario_ids, snakemake.input.choice_model, p.exclude, p.shift, p.tolerance,
          p.check_delta, p.mobile_share, p.credible_interval, snakemake.output.curve, snakemake.output.switches)
