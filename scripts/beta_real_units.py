"""Coefficients of the choice model in real units: beta_real = beta / sigma and gamma_real = gamma / sigma per
attribute and language region (posterior means), with the survey scale sigma from the model file."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS, ATTRIBUTE_UNITS, ATTRIBUTE_COLUMN_TO_MODEL_TERM
from load_data import load_beta_partworths_mean, load_mobile_partworths_mean
from utility import load_attribute_scale, to_real_units


def beta_real_table(path_to_choice_model: str, mobile_share: float, weights: dict = LANGUAGE_REGION_WEIGHTS) -> pd.DataFrame:
    scale = load_attribute_scale(path_to_choice_model)
    gamma = load_mobile_partworths_mean(path_to_choice_model).set_index("attribute")["mobile_mean"]
    gamma_real = to_real_units(gamma, scale, gamma.index)
    column_of = {term: col for col, term in ATTRIBUTE_COLUMN_TO_MODEL_TERM.items()}
    rows = []
    for region in weights:
        beta = load_beta_partworths_mean(path_to_choice_model, region).set_index("attribute")["beta_mean"]
        beta_real = to_real_units(beta, scale, beta.index)
        for term in beta.index:
            rows.append({"region": region, "attribute": term, "scenario_column": column_of[term], "sigma": scale[term], "beta_mean": beta[term],
                         "beta_real": beta_real[term], "gamma_mean": gamma[term], "gamma_real": gamma_real[term],
                         "mobile_share": mobile_share, "unit_of_raw_attribute": ATTRIBUTE_UNITS[term]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    beta_real_table(snakemake.input.choice_model, snakemake.params.mobile_share).to_csv(snakemake.output[0], index=False)
