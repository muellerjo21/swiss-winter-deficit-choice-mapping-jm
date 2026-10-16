"""Utility, 94% credible interval, P(rank 1) and rank per scenario and language region plus the
population-weighted national mean, compared with the cost rank from Mellot et al. (2024).

All uncertainty measures are derived deterministically from the posterior samples (chain x draw) of
the choice model -- no random sampling, hence exactly reproducible for identical input.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS
from load_data import (
    load_beta_partworths_mean, load_beta_partworths_samples,
    load_mobile_partworths_mean, load_mobile_partworths_samples,
)
from utility import load_attribute_scale, compute_regional_utilities, rank_scenarios

CI_QUANTILES = (0.03, 0.97)  # 94% credible interval, equal-tailed (not HDI)


def probability_rank1(samples: pd.DataFrame) -> pd.Series:
    """Share of posterior samples in which the scenario has the highest utility."""
    best = samples.columns[np.argmax(samples.to_numpy(), axis=1)]
    return pd.Series(best).value_counts(normalize=True).reindex(samples.columns, fill_value=0.0)


def build_rankings(attributes: pd.DataFrame, path_to_choice_model: str,
                   weights: dict = LANGUAGE_REGION_WEIGHTS, mobile_share: float = 0.0) -> pd.DataFrame:
    scale = load_attribute_scale(path_to_choice_model)
    betas_mean = {region: load_beta_partworths_mean(path_to_choice_model, region) for region in weights}
    betas_samples = {region: load_beta_partworths_samples(path_to_choice_model, region) for region in weights}
    mobile_mean = load_mobile_partworths_mean(path_to_choice_model)
    mobile_samples = load_mobile_partworths_samples(path_to_choice_model)
    utilities, samples = compute_regional_utilities(attributes, betas_mean, betas_samples, scale, weights,
                                                    mobile_mean, mobile_samples, mobile_share)
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

    # Cost rank: equal cost -> equal rank (S/CCGT pair), baseline (NaN) without a rank
    rankings["mellot_cost_change_pct"] = attributes.set_index("scenario_id")["mellot_cost_change_pct"]
    rankings["rank_mellot_cost"] = rankings["mellot_cost_change_pct"].rank(method="min")
    rankings["rank_diff_national_vs_mellot"] = rankings["rank_national"] - rankings["rank_mellot_cost"]
    return rankings.sort_values("utility_national", ascending=False).reset_index()


if __name__ == "__main__":
    build_rankings(
        attributes=pd.read_csv(snakemake.input.attributes),
        path_to_choice_model=snakemake.input.choice_model,
        mobile_share=snakemake.params.mobile_share,
    ).to_csv(snakemake.output[0], index=False)
