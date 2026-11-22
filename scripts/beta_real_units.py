"""Coefficients of the choice model in real units: beta_real = beta / sigma and gamma_real = gamma / sigma per
attribute and language region (posterior means), with the survey scale sigma from the model file (gamma = 0 for a
model without mobile shift). Plus a check of the Swiss coefficients (choice_model_check.csv): the loaded posterior
samples against the model's own variables draw by draw, and the model's utility u_right of the Swiss choice
situations recomputed from the scaled attributes for a few draws."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS, ATTRIBUTE_COLUMN_TO_MODEL_TERM, attribute_units
from load_data import load_beta_partworths_mean, load_beta_partworths_samples, load_mobile_partworths_mean
from utility import load_attribute_scale, to_real_units


def beta_real_table(path_to_choice_model: str, mobile_share: float, units: dict,
                    weights: dict = LANGUAGE_REGION_WEIGHTS) -> pd.DataFrame:
    scale = load_attribute_scale(path_to_choice_model)
    mobile = load_mobile_partworths_mean(path_to_choice_model)
    gamma = (pd.Series(0.0, index=list(scale)) if mobile is None   # model without mobile shift
             else mobile.set_index("attribute")["mobile_mean"])
    gamma_real = to_real_units(gamma, scale, gamma.index)
    column_of = {term: col for col, term in ATTRIBUTE_COLUMN_TO_MODEL_TERM.items()}
    rows = []
    for region in weights:
        beta = load_beta_partworths_mean(path_to_choice_model, region).set_index("attribute")["beta_mean"]
        beta_real = to_real_units(beta, scale, beta.index)
        for term in beta.index:
            rows.append({"region": region, "attribute": term, "scenario_column": column_of[term], "sigma": scale[term], "beta_mean": beta[term],
                         "beta_real": beta_real[term], "gamma_mean": gamma[term], "gamma_real": gamma_real[term],
                         "mobile_share": mobile_share, "unit_of_raw_attribute": units[term]})
    return pd.DataFrame(rows)


CHECK_DRAWS = [(0, 0), (1, 500), (3, 999)]  # (chain, draw) for the utility check


def coefficient_check(path_to_choice_model: str, coefficients: dict) -> pd.DataFrame:
    """Per Swiss coefficient group: the file's group/country, max |loaded samples - expected| over all draws, where
    expected = beta_partworths[country] (per-group file) or beta_partworths + effect_country[country], and
    max |u_right - sum_k x_right_scaled_k * beta_k| over the Swiss choice situations (CHECK_DRAWS; u_right contains
    no intercept, so it holds without mobile shift or for respondents with m = 0)."""
    post = xr.open_dataset(path_to_choice_model, group="posterior")
    const = xr.open_dataset(path_to_choice_model, group="constant_data")
    countries = [str(c) for c in post["country"].values]
    per_group = "country" in post["beta_partworths"].dims
    rows = []
    for group, country in coefficients.items():
        expected = (post["beta_partworths"].sel(country=country) if per_group
                    else post["beta_partworths"] + post["effect_country"].sel(country=country))
        stacked = expected.stack(sample=("chain", "draw"))
        loaded = load_beta_partworths_samples(path_to_choice_model, group)
        sample_diff = max(float(np.abs(loaded[a] - stacked.sel(attribute=a).values).max()) for a in loaded)
        situations = np.where(const["c"].values == countries.index(country))[0]
        if "m" in const:  # u_right includes the mobile shift for m = 1: check m = 0 only
            situations = situations[const["m"].values[situations] == 0]
        x = const["attribute_values_right_scaled"].isel(choice_situation=situations).transpose(..., "attribute")
        utility_diff = max(float(np.abs(post["u_right"].isel(chain=c, draw=d, choice_situation=situations).values
                                        - (x.values * expected.isel(chain=c, draw=d).sel(attribute=x["attribute"]).values).sum(1)).max())
                           for c, d in CHECK_DRAWS)
        rows.append({"group": group, "model_country": country, "structure": "per group" if per_group else "mean + country effect",
                     "n_samples": stacked.sizes["sample"], "max_abs_diff_samples": sample_diff,
                     "n_situations": len(situations), "max_abs_diff_u_right": utility_diff})
    post.close(); const.close()
    return pd.DataFrame(rows)


if __name__ == "__main__":
    p = snakemake.params
    units = attribute_units(p.cost_scope, p.import_definition, p.import_denominator)
    beta_real_table(snakemake.input.choice_model, p.mobile_share, units).to_csv(snakemake.output.table, index=False)
    coefficient_check(snakemake.input.choice_model, snakemake.params.coefficients).to_csv(snakemake.output.check, index=False)
