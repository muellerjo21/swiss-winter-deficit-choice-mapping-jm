"""
Utility computation for the Mellot scenarios with the Jan 2026 choice model (CHOICE_MODEL_PATH).

The model is fitted on scaled attribute values (constant_data/attribute_values_*_scaled =
raw value / survey maximum, e.g. import/0.9, land/0.08, transmission/2.0). The scenario attributes
(raw values, as in scenario_attributes_summary) are therefore divided by the same factors before
being multiplied by beta -- verified against u_right in the posterior (deviation ~1e-15):
    u = sum_k x_scaled[k] * (beta_partworths[country, k] + m * mobile_partworths[k])
(m in constant_data, 0/1 per respondent; also verified against u_left/u_right, ~1e-16).
beta_partworths alone is the reference case m=0. Optionally, mobile_partworths is mixed in with the
share mobile_share (0..1, config/default.yaml utility.mobile_share); default 0.0 = reference case.
left_intercept (left/right position effect) is deliberately not used.
"""

import arviz as az
import numpy as np
import pandas as pd

from config import ATTRIBUTE_COLUMN_TO_MODEL_TERM, LANGUAGE_REGION_WEIGHTS


def load_attribute_scale(data_path) -> dict:
    """Scaling factor per model attribute (raw value / scaled value), read directly from the
    survey data in the model file instead of hard-coded."""
    constant = az.from_netcdf(data_path).constant_data
    raw = constant["attribute_values_left"].max(dim="choice_situation")
    scaled = constant["attribute_values_left_scaled"].max(dim="choice_situation")
    return (raw / scaled).to_series().to_dict()


def scale_scenario_attributes(scenario_row: pd.Series, scale: dict,
                              mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM) -> pd.Series:
    """Raw scenario values -> scaled values, indexed by model attribute name."""
    return pd.Series({term: scenario_row[col] / scale[term] for col, term in mapping.items()})


def _check_mobile_share(mobile_share: float, mobile) -> None:
    if not 0.0 <= mobile_share <= 1.0:
        raise ValueError(f"mobile_share must be between 0 and 1, got {mobile_share}")
    if mobile_share != 0.0 and mobile is None:
        raise ValueError("mobile partworths are required when mobile_share is non-zero")


def compute_utility(scenario_row: pd.Series, beta: pd.DataFrame, scale: dict,
                    mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM,
                    mobile: pd.DataFrame = None, mobile_share: float = 0.0) -> float:
    """Point estimate: sum((beta_mean + mobile_share * mobile_mean) * x_scaled) over all 11
    attributes. beta as returned by load_beta_partworths_mean() (columns attribute, beta_mean), mobile
    as returned by load_mobile_partworths_mean() (columns attribute, mobile_mean); only needed if
    mobile_share > 0."""
    _check_mobile_share(mobile_share, mobile)
    x = scale_scenario_attributes(scenario_row, scale, mapping)
    coef = beta.set_index("attribute")["beta_mean"].loc[x.index]
    if mobile_share != 0.0:
        coef = coef + mobile_share * mobile.set_index("attribute")["mobile_mean"].loc[x.index]
    return float((x * coef).sum())


def compute_utility_samples(scenario_row: pd.Series, beta_samples: dict, scale: dict,
                            mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM,
                            mobile_samples: dict = None, mobile_share: float = 0.0) -> np.ndarray:
    """Utility per posterior sample (array of length chains*draws), same sample order as
    beta_samples (from load_beta_partworths_samples()). If mobile_share > 0, per sample i:
    x * (beta[i] + mobile_share * mobile[i]); mobile_samples from load_mobile_partworths_samples()
    is stacked the same way, so sample i belongs to the same posterior draw across all attributes."""
    _check_mobile_share(mobile_share, mobile_samples)
    x = scale_scenario_attributes(scenario_row, scale, mapping)
    if mobile_share == 0.0:
        return sum(x[term] * beta_samples[term] for term in x.index)
    return sum(x[term] * (beta_samples[term] + mobile_share * mobile_samples[term]) for term in x.index)


def compute_regional_utilities(scenarios: pd.DataFrame, betas_mean: dict, betas_samples: dict,
                               scale: dict, weights: dict = LANGUAGE_REGION_WEIGHTS,
                               mobile_mean: pd.DataFrame = None, mobile_samples: dict = None,
                               mobile_share: float = 0.0) -> tuple:
    """Utility per scenario and language region (keys of weights) plus the population-weighted
    national mean. mobile_mean/mobile_samples apply to all regions (mobile_partworths has no
    country dimension) and are mixed in with mobile_share (see compute_utility).

    Returns
    -------
    (utilities, samples)
        utilities: DataFrame with scenario_id, utility_<region> and utility_national (mean betas).
        samples: dict region/"national" -> DataFrame (sample x scenario).
    """
    utilities = pd.DataFrame({"scenario_id": scenarios["scenario_id"]})
    samples = {}
    for region in weights:
        col = f"utility_{region.replace('-', '_')}"
        utilities[col] = [compute_utility(row, betas_mean[region], scale,
                                          mobile=mobile_mean, mobile_share=mobile_share)
                          for _, row in scenarios.iterrows()]
        samples[region] = pd.DataFrame({row["scenario_id"]: compute_utility_samples(row, betas_samples[region], scale,
                                                                                     mobile_samples=mobile_samples,
                                                                                     mobile_share=mobile_share)
                                        for _, row in scenarios.iterrows()})
    utilities["utility_national"] = sum(
        w * utilities[f"utility_{region.replace('-', '_')}"] for region, w in weights.items()
    )
    samples["national"] = sum(w * samples[region] for region, w in weights.items())
    return utilities, samples


def rank_scenarios(utilities: pd.DataFrame, column: str) -> pd.DataFrame:
    """Ranking sorted by descending utility (rank 1 = highest predicted preference)."""
    ranked = utilities[["scenario_id", column]].sort_values(column, ascending=False).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    return ranked


def compute_pairwise_choice_probability(utility_a, utility_b):
    """P(scenario A is preferred over B), standard logit link -- identical to the link in the
    choice model (p_left = sigmoid(u_left - u_right), verified against the posterior).
    Works for floats (mean utility) and element-wise for sample arrays."""
    return 1 / (1 + np.exp(-(np.asarray(utility_a) - np.asarray(utility_b))))


def compute_choice_shares(utilities: dict) -> dict:
    """Share if all scenarios were available for choice at the same time (softmax, IIA assumption --
    methodologically a stronger assumption than the pairwise comparison, as it does not match the
    original survey design with pairwise comparisons).
    Values may be floats or sample arrays of equal length (softmax is then applied per sample)."""
    names = list(utilities)
    u = np.stack([np.asarray(utilities[k], dtype=float) for k in names])
    exp_u = np.exp(u - u.max(axis=0))  # numerically stable, result unchanged
    shares = exp_u / exp_u.sum(axis=0)
    return {k: shares[i] if shares.ndim > 1 else float(shares[i]) for i, k in enumerate(names)}
