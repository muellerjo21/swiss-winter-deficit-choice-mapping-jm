"""Pairwise choice probabilities of the regional main analysis (src/pairwise.py): matrix over all scenario pairs,
per-region table for the map pairs, comparison of the two aggregations, checks."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_LANGUAGE, LANGUAGE_REGION_WEIGHTS
from pairwise import aggregation_comparison, checks, pairwise_matrix, region_pair_table, scenario_order
from regional import load_regional_model, population_weights, regional_utilities


if __name__ == "__main__":
    p = snakemake.params
    attributes = pd.read_csv(snakemake.input.attributes)
    population = pd.read_csv(snakemake.input.population).set_index("region")["population"]
    weights = population_weights(population, p.exclude)
    coefficients = {r: CANTON_LANGUAGE.get(r) for r in population.index}
    model = load_regional_model(snakemake.input.choice_model, p.mobile_share, LANGUAGE_REGION_WEIGHTS)
    _, _, _, region_samples = regional_utilities(attributes, weights, coefficients, **model)
    cost = attributes.drop_duplicates("scenario_id").set_index("scenario_id")["mellot_cost_change_pct"].reindex(p.scenario_ids)
    order = scenario_order(cost, p.order)
    matrix = pairwise_matrix(region_samples, weights, order, p.credible_interval)
    matrix.to_csv(snakemake.output.matrix, index=False)
    regions = pd.concat([region_pair_table(region_samples, a, b, p.credible_interval) for a, b in p.map_pairs],
                        ignore_index=True)
    regions.to_csv(snakemake.output.regions, index=False)
    for (a, b), path in zip(p.map_pairs, snakemake.output.map_tables):
        regions[(regions["scenario_1"] == a) & (regions["scenario_2"] == b)].to_csv(path, index=False)
    aggregation_comparison(matrix).to_csv(snakemake.output.comparison, index=False)
    checks(matrix, regions, region_samples, weights, p.credible_interval).to_csv(snakemake.output.checks, index=False)
