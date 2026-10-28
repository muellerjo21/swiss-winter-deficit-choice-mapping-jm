"""Pairwise choice probabilities of the regional main analysis, as in Tröndle et al. (2025), Fig. 2/4 (matrix)
and Fig. 1/3 (maps).

Per posterior draw i and region j: p_{A>B,j,i} = logistic(u_{A,j,i} - u_{B,j,i}). National per draw:
P_i(A>B) = sum_j w_j p_{A>B,j,i} (population-weighted mean of the regional choice probabilities, not of the
utilities). Expected value = mean over the draws, interval = equal-tailed credible interval. For comparison, the
previous aggregation logistic(sum_j w_j u_{A,j,i} - sum_j w_j u_{B,j,i}) is reported alongside.
"""
import numpy as np
import pandas as pd

from utility import compute_pairwise_choice_probability, credible_interval_quantiles


def scenario_order(cost: pd.Series, explicit: list = None) -> list:
    """Scenario order of the matrix: explicit list if given, else by cost change ascending (cheapest first, ties
    in the order of `cost`), scenarios without a cost value last."""
    if explicit:
        missing = set(cost.index) ^ set(explicit)
        if missing:
            raise ValueError(f"pairwise.scenario_order must list every scenario exactly once: {sorted(missing)}")
        return list(explicit)
    with_cost = cost.dropna().sort_values(kind="stable")
    return list(with_cost.index) + [s for s in cost.index if pd.isna(cost[s])]


def _interval(values: np.ndarray, credible_interval: float) -> tuple[float, float, float]:
    low, high = credible_interval_quantiles(credible_interval)
    return float(values.mean()), float(np.quantile(values, low)), float(np.quantile(values, high))


def regional_pair_draws(region_samples: dict, weights: pd.Series, a: str, b: str) -> tuple[np.ndarray, np.ndarray]:
    """(sum_j w_j p_{A>B,j,i}, logistic(sum_j w_j u_{A,j,i} - sum_j w_j u_{B,j,i})) per draw i."""
    prob = sum(weights[j] * compute_pairwise_choice_probability(region_samples[j][a].to_numpy(),
                                                                region_samples[j][b].to_numpy())
               for j in weights.index)
    u_a = sum(weights[j] * region_samples[j][a].to_numpy() for j in weights.index)
    u_b = sum(weights[j] * region_samples[j][b].to_numpy() for j in weights.index)
    return np.asarray(prob, dtype=float), compute_pairwise_choice_probability(u_a, u_b)


def pairwise_matrix(region_samples: dict, weights: pd.Series, order: list, credible_interval: float) -> pd.DataFrame:
    """All ordered pairs (incl. the diagonal) in matrix order: expected value and interval of P(scenario 1 >
    scenario 2) aggregated over the regions, and the expected value of the utility aggregation."""
    rows = []
    for i, a in enumerate(order):
        for k, b in enumerate(order):
            prob, via_utility = regional_pair_draws(region_samples, weights, a, b)
            mean, low, high = _interval(prob, credible_interval)
            rows.append({"scenario_1": a, "scenario_2": b, "row": i, "column": k, "p_mean": mean, "p_low": low,
                         "p_high": high, "p_mean_utility_aggregation": float(via_utility.mean())})
    out = pd.DataFrame(rows)
    out["abs_diff_aggregation"] = (out["p_mean"] - out["p_mean_utility_aggregation"]).abs()
    return out


def region_pair_table(region_samples: dict, a: str, b: str, credible_interval: float) -> pd.DataFrame:
    """Per region: expected value and interval of P(a > b) over the draws."""
    rows = []
    for j, samples in region_samples.items():
        p = compute_pairwise_choice_probability(samples[a].to_numpy(), samples[b].to_numpy())
        mean, low, high = _interval(p, credible_interval)
        rows.append({"region": j, "scenario_1": a, "scenario_2": b, "p_mean": mean, "p_low": low, "p_high": high})
    return pd.DataFrame(rows)


def aggregation_comparison(matrix: pd.DataFrame) -> pd.DataFrame:
    """Deviation between the aggregation of the probabilities and of the utilities, off-diagonal pairs."""
    off = matrix[matrix["scenario_1"] != matrix["scenario_2"]]
    d = off["abs_diff_aggregation"]
    worst = off.loc[d.idxmax()]
    return pd.DataFrame([{"n_pairs": len(off), "max_abs_diff": d.max(), "mean_abs_diff": d.mean(),
                          "max_pair_scenario_1": worst["scenario_1"], "max_pair_scenario_2": worst["scenario_2"],
                          "max_pair_p_mean": worst["p_mean"],
                          "max_pair_p_mean_utility_aggregation": worst["p_mean_utility_aggregation"]}])


def checks(matrix: pd.DataFrame, regions: pd.DataFrame, region_samples: dict, weights: pd.Series,
           credible_interval: float) -> pd.DataFrame:
    """Consistency checks: (name, value, tolerance)."""
    m = matrix.set_index(["scenario_1", "scenario_2"])
    swapped = m["p_mean"].reindex([(b, a) for a, b in m.index]).to_numpy()
    diag = matrix[matrix["scenario_1"] == matrix["scenario_2"]]
    values = np.concatenate([matrix[["p_mean", "p_low", "p_high", "p_mean_utility_aggregation"]].to_numpy().ravel(),
                             regions[["p_mean", "p_low", "p_high"]].to_numpy().ravel()])
    out_of_range = int(((values < 0) | (values > 1)).sum())
    rows = [("weights sum to 1", abs(weights.sum() - 1), 1e-12),
            ("p(A>B) + p(B>A) = 1", float(np.abs(m["p_mean"].to_numpy() + swapped - 1).max()), 1e-12),
            ("diagonal = 0.5", float((diag[["p_mean", "p_low", "p_high"]] - 0.5).abs().to_numpy().max()), 1e-15),
            ("probabilities in [0, 1]", float(out_of_range), 0),
            ("interval contains the mean", float(((matrix["p_low"] > matrix["p_mean"] + 1e-15)
                                                  | (matrix["p_high"] < matrix["p_mean"] - 1e-15)).sum()), 0)]
    # single region: weight 1 on one region must give that region's own probabilities (for every map pair and region)
    dev = 0.0
    for (a, b), table in regions.groupby(["scenario_1", "scenario_2"]):
        for _, r in table.iterrows():
            one = pd.Series(1.0, index=[r["region"]])
            prob, _ = regional_pair_draws(region_samples, one, a, b)
            mean, low, high = _interval(prob, credible_interval)
            dev = max(dev, abs(mean - r["p_mean"]), abs(low - r["p_low"]), abs(high - r["p_high"]))
    rows.append(("single region = region table", dev, 1e-15))
    # national expected value = population-weighted mean of the regional expected values (linearity)
    dev = 0.0
    for (a, b), table in regions.groupby(["scenario_1", "scenario_2"]):
        national = m.loc[(a, b), "p_mean"]
        dev = max(dev, abs(national - (table.set_index("region")["p_mean"] * weights).sum()))
    rows.append(("national mean = weighted mean of regional means", dev, 1e-12))
    out = pd.DataFrame(rows, columns=["check", "value", "tolerance"])
    out["passed"] = out["value"] <= out["tolerance"]
    return out
