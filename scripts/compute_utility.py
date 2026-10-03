"""Utility, 94%-Credible-Interval, P(Rang 1) und Rang pro Szenario und Sprachregion plus
bevölkerungsgewichtetes nationales Mittel, verglichen mit dem Kostenrang aus Mellot et al. (2024).

Alle Unsicherheitsmasse beruhen deterministisch auf den Posterior-Samples (chain x draw) des
Choice-Modells -- kein Zufallsziehen, daher bei gleichem Input exakt reproduzierbar.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS
from load_data import load_beta_partworths_mean, load_beta_partworths_samples
from utility import load_attribute_scale, compute_regional_utilities, rank_scenarios

CI_QUANTILES = (0.03, 0.97)  # 94%-Credible-Interval, gleichschwänzig (nicht HDI)


def probability_rank1(samples: pd.DataFrame) -> pd.Series:
    """Anteil der Posterior-Samples, in denen das Szenario die höchste Utility hat."""
    best = samples.columns[np.argmax(samples.to_numpy(), axis=1)]
    return pd.Series(best).value_counts(normalize=True).reindex(samples.columns, fill_value=0.0)


def build_rankings(attributes: pd.DataFrame, path_to_choice_model: str,
                   weights: dict = LANGUAGE_REGION_WEIGHTS) -> pd.DataFrame:
    scale = load_attribute_scale(path_to_choice_model)
    betas_mean = {region: load_beta_partworths_mean(path_to_choice_model, region) for region in weights}
    betas_samples = {region: load_beta_partworths_samples(path_to_choice_model, region) for region in weights}
    utilities, samples = compute_regional_utilities(attributes, betas_mean, betas_samples, scale, weights)
    rankings = utilities.set_index("scenario_id")

    for region in [*weights, "national"]:
        tag = region.replace("-", "_")
        col = f"utility_{tag}"
        ranked = rank_scenarios(utilities, col).set_index("scenario_id")
        ci = samples[region].quantile(list(CI_QUANTILES))
        rankings[f"rank_{tag}"] = ranked["rank"]
        rankings[f"{col}_ci94_low"] = ci.loc[CI_QUANTILES[0]]
        rankings[f"{col}_ci94_high"] = ci.loc[CI_QUANTILES[1]]
        rankings[f"p_rank1_{tag}"] = probability_rank1(samples[region])

    # Kostenrang: gleiche Kosten -> gleicher Rang (S/CCGT-Paar), baseline (NaN) ohne Rang
    rankings["mellot_cost_change_pct"] = attributes.set_index("scenario_id")["mellot_cost_change_pct"]
    rankings["rank_mellot_cost"] = rankings["mellot_cost_change_pct"].rank(method="min")
    rankings["rank_diff_national_vs_mellot"] = rankings["rank_national"] - rankings["rank_mellot_cost"]
    return rankings.sort_values("utility_national", ascending=False).reset_index()


if __name__ == "__main__":
    build_rankings(
        attributes=pd.read_csv(snakemake.input.attributes),
        path_to_choice_model=snakemake.input.choice_model,
    ).to_csv(snakemake.output[0], index=False)
