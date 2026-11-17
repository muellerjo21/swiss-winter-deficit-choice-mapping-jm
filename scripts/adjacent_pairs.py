"""Neighbouring ranks of the national ranking per weather year (main analysis). For every pair of neighbouring ranks
(A = rank r, B = rank r+1, order by posterior-mean national utility):
- utility_diff: difference of the posterior-mean national utilities;
- p_a_higher_utility: share of posterior draws in which A has the higher national utility (how certain the order is;
  ranks with p_a_higher_utility < 0.95 are reported as tied, a convention of this project);
- p_a_chosen_over_b: pairwise choice probability as in the pipeline (per region and draw logistic(u_A - u_B),
  population-weighted, mean over draws).
Inputs: the regional attributes of the weather-year runs (rule weather_year_rankings) and the choice model of
config/default.yaml. Run with the Python of the workflow's conda environment from the project root:
    python scripts/adjacent_pairs.py build/data docs/adjacent_pairs.csv"""
import sys
import numpy as np, pandas as pd, yaml
sys.path.insert(0, "src")
from config import LANGUAGE_REGION_WEIGHTS
from regional import load_regional_model, population_weights, region_coefficients, regional_utilities

data, out = sys.argv[1], sys.argv[2]
cfg = yaml.safe_load(open("config/default.yaml"))
model = load_regional_model(cfg["data"]["choice_models"][cfg["data"]["choice_model"]]["file"],
                            cfg["utility"]["mobile_share"], LANGUAGE_REGION_WEIGHTS)
population = pd.read_csv("data/processed/population_by_region.csv").set_index("region")["population"]
weights = population_weights(population, [])
coef = region_coefficients(population.index, {"TI": "DE-CH"})
rows = []
for y in cfg["sensitivity"]["weather_years"]:
    a = pd.read_csv(f"{data}/weather/{y}/regional_attributes.csv")
    u, samples, points, region_samples = regional_utilities(a, weights, coef, **model)
    nat = samples["national"]                      # draws x scenarios
    order = u.set_index("scenario_id")["utility_national"].sort_values(ascending=False)
    for r, (sa, sb) in enumerate(zip(order.index[:-1], order.index[1:]), start=1):
        p_order = float((nat[sa] > nat[sb]).mean())
        choice = sum(weights[j] / (1 + np.exp(-(region_samples[j][sa] - region_samples[j][sb]))) for j in weights.index)
        rows.append({"weather_year": y, "rank_a": r, "scenario_a": sa, "scenario_b": sb,
                     "utility_a": order[sa], "utility_b": order[sb], "utility_diff": order[sa] - order[sb],
                     "p_a_higher_utility": p_order, "p_a_chosen_over_b": float(np.mean(choice))})
pd.DataFrame(rows).to_csv(out, index=False)
print(len(rows), "pairs")
