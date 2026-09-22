import pandas as pd
import numpy as np

from config import ATTRIBUTE_MAX_VALUES, SWISS_LAND_AREA_KM2, TECHNOLOGY_KEYS

# TECHNOLOGY_KEYS holds the fitted technologies (e.g. "TECHNOLOGY:Open-field PV").
# "Rooftop PV" is the implicit reference category (beta = 0, no key in the model),
# so it's added here explicitly as the one allowed value with no matching key.
VALID_TECHNOLOGIES = {key.split(":", 1)[1] for key in TECHNOLOGY_KEYS} | {"Rooftop PV"}


def scale_attribute(raw_value: float, attribute: str) -> float:
    """Scale a raw (decimal) attribute value to the 0-1 scale the model was fitted on."""
    return raw_value / ATTRIBUTE_MAX_VALUES[attribute]


def compute_utility(
    scenario_row: pd.Series,
    beta_means: pd.DataFrame,
    dominant_technology: str,
    share_imports: float = 0.0,
    transmission: float = 0.0,
) -> dict:
    """
    Compute the utility of one Mellot scenario under the fitted choice model.

    Parameters
    ----------
    scenario_row : one row of scenarios_data (from mellot_scenarios.csv)
    beta_means : DataFrame with columns ["attribute", "beta_mean"],
        as returned by load_beta_partworths_mean()
    dominant_technology : one of VALID_TECHNOLOGIES
        (Rooftop PV = reference category, all technology flags = 0).
        Passed explicitly — not inferred from the CSV — because this is
        a mapping decision (capacity share vs. generation share, etc.)
        that you make per scenario, not raw data.
    share_imports : placeholder until real annual generation/demand data
        is available (currently 0.0 for all scenarios).
    transmission : placeholder until the transmission-capacity question
        is resolved with Tim (currently 0.0 for all scenarios).

    Returns
    -------
    dict with keys: "utility" (float, total) and "contributions"
        (dict of attribute -> x*beta, for inspection/debugging).
    """
    if dominant_technology not in VALID_TECHNOLOGIES:
        raise ValueError(
            f"dominant_technology must be one of {VALID_TECHNOLOGIES}, "
            f"got {dominant_technology!r}"
        )

    land_share = scenario_row["land_use_km2_approx"] / SWISS_LAND_AREA_KM2
    land_scaled = scale_attribute(land_share, "LAND")

    price_raw_decimal = scenario_row["cost_change_pct_vs_ep2050"] / 100
    price_scaled = scale_attribute(price_raw_decimal, "PRICES")

    x = {
        key: 1 if key == f"TECHNOLOGY:{dominant_technology}" else 0
        for key in TECHNOLOGY_KEYS
    }
    x.update({
        "TRANSMISSION": transmission,
        "LAND": land_scaled,
        "SHARE_IMPORTS": share_imports,
        "PRICES": price_scaled,
    })

    contributions = {}
    for attr, x_val in x.items():
        beta_val = beta_means.loc[beta_means["attribute"] == attr, "beta_mean"].values[0]
        contributions[attr] = x_val * beta_val

    utility = sum(contributions.values())

    return {"utility": utility, "contributions": contributions}

def compute_probabilities(utilities: dict, choice_set: list = None) -> dict:
    """
    Convert utilities into multinomial logit choice probabilities.

    Parameters
    ----------
    utilities : dict of {scenario_name: utility_value}
        Typically {name: result["utility"] for name, result in results.items()}
    choice_set : list of scenario names to include in the softmax denominator.
        If None, uses all scenarios in `utilities`.

    Returns
    -------
    dict of {scenario_name: probability}, only for scenarios in choice_set.
    """
    if choice_set is None:
        choice_set = list(utilities.keys())

    relevant = {name: utilities[name] for name in choice_set}
    exp_u = {name: np.exp(u) for name, u in relevant.items()}
    total = sum(exp_u.values())

    return {name: val / total for name, val in exp_u.items()}