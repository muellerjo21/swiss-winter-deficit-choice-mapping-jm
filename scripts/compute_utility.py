"""Utility, credible interval (utility.credible_interval, default 94%), P(rank 1) and rank per scenario
and language region plus the population-weighted national mean, compared with the cost rank from Mellot et al. (2024).

All uncertainty measures are derived deterministically from the posterior samples (chain x draw) of
the choice model -- no random sampling, hence exactly reproducible for identical input.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS, CREDIBLE_INTERVAL
from load_data import (
    load_beta_partworths_mean, load_beta_partworths_samples,
    load_mobile_partworths_mean, load_mobile_partworths_samples,
)
from utility import load_attribute_scale, rank_with_uncertainty


def build_rankings(attributes: pd.DataFrame, path_to_choice_model: str,
                   weights: dict = LANGUAGE_REGION_WEIGHTS, mobile_share: float = 0.0,
                   credible_interval: float = CREDIBLE_INTERVAL) -> pd.DataFrame:
    scale = load_attribute_scale(path_to_choice_model)
    betas_mean = {region: load_beta_partworths_mean(path_to_choice_model, region) for region in weights}
    betas_samples = {region: load_beta_partworths_samples(path_to_choice_model, region) for region in weights}
    mobile_mean = load_mobile_partworths_mean(path_to_choice_model)
    mobile_samples = load_mobile_partworths_samples(path_to_choice_model)
    return rank_with_uncertainty(attributes, betas_mean, betas_samples, scale, weights,
                                 mobile_mean, mobile_samples, mobile_share, credible_interval)


if __name__ == "__main__":
    build_rankings(
        attributes=pd.read_csv(snakemake.input.attributes),
        path_to_choice_model=snakemake.input.choice_model,
        mobile_share=snakemake.params.mobile_share,
        credible_interval=snakemake.params.credible_interval,
    ).to_csv(snakemake.output[0], index=False)
