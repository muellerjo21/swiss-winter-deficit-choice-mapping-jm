"""
Utility computation for the Mellot scenarios with the Jan 2026 choice model (CHOICE_MODEL_PATH).

The model is fitted on scaled attribute values z / sigma_k (constant_data/attribute_values_*_scaled =
raw value / survey maximum sigma_k, e.g. import 0.9, land 0.08, transmission 2.0; read from the model
file by load_attribute_scale). Instead of scaling the scenario attributes, the coefficients are
converted back to real units, which is mathematically identical (z / sigma * beta = z * (beta / sigma)):
    beta_real_k  = beta_partworths[country, k] / sigma_k   (utility per unit of the raw attribute)
    gamma_real_k = mobile_partworths[k] / sigma_k
    u = sum_k z_k * (beta_real_k + mobile_share * gamma_real_k)
with z the raw scenario attributes as in scenario_attributes_summary (shares 0..1, relative price
change, land share). The model form u = sum_k z_k / sigma_k * (beta + m * gamma) was verified against
u_left/u_right in the posterior (deviation ~1e-16; m in constant_data, 0/1 per respondent).
beta alone is the reference case m=0; mobile_share (0..1, config/default.yaml utility.mobile_share)
mixes in gamma, default 0.0. left_intercept (left/right position effect) is deliberately not used.
The equivalence holds because no attribute is clipped to the survey range after scaling (import_share
is clipped to [0, 1] on the raw value, before any coefficient is applied).
"""

import arviz as az
import numpy as np
import pandas as pd

from config import ATTRIBUTE_COLUMN_TO_MODEL_TERM, LANGUAGE_REGION_WEIGHTS, CREDIBLE_INTERVAL


def attribute_scale_from_constant_data(constant) -> dict:
    """Scaling factor sigma_k per model attribute (raw value / scaled value of the survey attributes,
    in the unit of the raw attribute), from the constant_data group of the model file."""
    raw = constant["attribute_values_left"].max(dim="choice_situation")
    scaled = constant["attribute_values_left_scaled"].max(dim="choice_situation")
    return (raw / scaled).to_series().to_dict()


def load_attribute_scale(data_path) -> dict:
    """sigma_k per model attribute, read directly from the survey data in the model file instead of
    hard-coded (see attribute_scale_from_constant_data)."""
    return attribute_scale_from_constant_data(az.from_netcdf(data_path).constant_data)


def raw_attributes(scenario_row: pd.Series, mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM) -> pd.Series:
    """Raw scenario attributes z (as in scenario_attributes_summary), indexed by model attribute name."""
    return pd.Series({term: scenario_row[col] for col, term in mapping.items()})


def to_real_units(coefficients, scale: dict, terms) -> dict:
    """Coefficients per model attribute (beta or gamma, utility per unit of the scaled attribute) ->
    real units (utility per unit of the raw attribute): coefficient_k / sigma_k. coefficients: mapping
    term -> float or array (posterior samples, order unchanged)."""
    return {t: coefficients[t] / scale[t] for t in terms}

def _check_mobile_share(mobile_share: float, mobile) -> None:
    if not 0.0 <= mobile_share <= 1.0:
        raise ValueError(f"mobile_share must be between 0 and 1, got {mobile_share}")
    if mobile_share != 0.0 and mobile is None:
        raise ValueError("mobile partworths are required when mobile_share is non-zero")


def compute_utility(scenario_row: pd.Series, beta: pd.DataFrame, scale: dict,
                    mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM,
                    mobile: pd.DataFrame = None, mobile_share: float = 0.0) -> float:
    """Point estimate: sum_k z_k * (beta_real_k + mobile_share * gamma_real_k) over all 11 attributes,
    with raw attributes z and coefficients in real units (to_real_units). beta as returned by
    load_beta_partworths_mean() (columns attribute, beta_mean), mobile as returned by
    load_mobile_partworths_mean() (columns attribute, mobile_mean); only needed if mobile_share > 0."""
    _check_mobile_share(mobile_share, mobile)
    z = raw_attributes(scenario_row, mapping)
    coef = pd.Series(to_real_units(beta.set_index("attribute")["beta_mean"], scale, z.index))
    if mobile_share != 0.0:
        coef = coef + mobile_share * pd.Series(to_real_units(mobile.set_index("attribute")["mobile_mean"], scale, z.index))
    return float((z * coef).sum())


def compute_utility_samples(scenario_row: pd.Series, beta_samples: dict, scale: dict,
                            mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM,
                            mobile_samples: dict = None, mobile_share: float = 0.0) -> np.ndarray:
    """Utility per posterior sample (array of length chains*draws), same sample order as
    beta_samples (from load_beta_partworths_samples()): per sample i,
    sum_k z_k * (beta_real_k[i] + mobile_share * gamma_real_k[i]) with raw attributes z and
    coefficients in real units. mobile_samples from load_mobile_partworths_samples() is stacked the
    same way, so sample i belongs to the same posterior draw across all attributes."""
    _check_mobile_share(mobile_share, mobile_samples)
    z = raw_attributes(scenario_row, mapping)
    beta_real = to_real_units(beta_samples, scale, z.index)
    if mobile_share == 0.0:
        return sum(z[term] * beta_real[term] for term in z.index)
    gamma_real = to_real_units(mobile_samples, scale, z.index)
    return sum(z[term] * (beta_real[term] + mobile_share * gamma_real[term]) for term in z.index)


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


def credible_interval_quantiles(probability: float) -> tuple[float, float]:
    """Lower and upper quantile of the equal-tailed (not HDI) credible interval with the given probability
    mass: (1-p)/2 and 1-(1-p)/2. Rounded to 12 decimals, because e.g. (1-0.94)/2 is 0.030000000000000027 in
    floating point; rounding gives exactly (0.03, 0.97) and thus unchanged quantiles."""
    tail = (1 - probability) / 2
    return round(tail, 12), round(1 - tail, 12)


def credible_interval_tag(probability: float) -> str:
    """Column tag of the interval, e.g. 'ci94' for 0.94 (utility_<region>_ci94_low/high)."""
    return f"ci{probability * 100:g}"


CI_QUANTILES = credible_interval_quantiles(CREDIBLE_INTERVAL)  # equal-tailed (not HDI), utility.credible_interval


def probability_rank1(samples: pd.DataFrame) -> pd.Series:
    """Share of posterior samples in which the scenario has the highest utility."""
    best = samples.columns[np.argmax(samples.to_numpy(), axis=1)]
    return pd.Series(best).value_counts(normalize=True).reindex(samples.columns, fill_value=0.0)


def rank_with_uncertainty(attributes: pd.DataFrame, betas_mean: dict, betas_samples: dict, scale: dict,
                          weights: dict = LANGUAGE_REGION_WEIGHTS, mobile_mean: pd.DataFrame = None,
                          mobile_samples: dict = None, mobile_share: float = 0.0,
                          credible_interval: float = CREDIBLE_INTERVAL) -> pd.DataFrame:
    """Utility, equal-tailed credible interval (probability credible_interval), P(rank 1) and rank per
    scenario and region (keys of weights) plus national, and the Mellot cost rank, for already loaded
    betas (see scripts/compute_utility.py). Sorted by descending national utility."""
    utilities, samples = compute_regional_utilities(attributes, betas_mean, betas_samples, scale, weights,
                                                    mobile_mean, mobile_samples, mobile_share)
    return rankings_from_utilities(utilities, samples, [*weights, "national"], attributes, credible_interval)


def rankings_from_utilities(utilities: pd.DataFrame, samples: dict, groups: list, attributes: pd.DataFrame,
                            credible_interval: float = CREDIBLE_INTERVAL) -> pd.DataFrame:
    """Rank, equal-tailed credible interval and P(rank 1) per group (columns utility_<group> in utilities,
    posterior samples in samples[group]) plus the Mellot cost rank; used for the national and the regional
    analysis. Sorted by descending national utility."""
    quantiles, ci_tag = credible_interval_quantiles(credible_interval), credible_interval_tag(credible_interval)
    rankings = utilities.set_index("scenario_id")

    for region in groups:
        tag = region.replace("-", "_")
        col = f"utility_{tag}"
        ranked = rank_scenarios(utilities, col).set_index("scenario_id")
        ci = samples[region].quantile(list(quantiles))
        rankings[f"rank_{tag}"] = ranked["rank"]
        rankings[f"{col}_{ci_tag}_low"] = ci.loc[quantiles[0]]
        rankings[f"{col}_{ci_tag}_high"] = ci.loc[quantiles[1]]
        rankings[f"p_rank1_{tag}"] = probability_rank1(samples[region])

    # Cost rank: equal cost -> equal rank (S/CCGT pair), baseline (NaN) without a rank
    rankings["mellot_cost_change_pct"] = attributes.set_index("scenario_id")["mellot_cost_change_pct"]
    rankings["rank_mellot_cost"] = rankings["mellot_cost_change_pct"].rank(method="min")
    rankings["rank_diff_national_vs_mellot"] = rankings["rank_national"] - rankings["rank_mellot_cost"]
    return rankings.sort_values("utility_national", ascending=False).reset_index()


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
