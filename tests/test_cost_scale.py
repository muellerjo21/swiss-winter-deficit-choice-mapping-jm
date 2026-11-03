"""Tests of the cost-factor switch (price.cost_scale_factor) and its sensitivity (rule cost_scale_regional): the
factor applied in the main analysis is reproduced by the sweep, the price-year conversions (cost_scale_conversions)
give the documented factors, the price attribute (and hence the utility) is linear in the factor, a higher factor
lowers every utility, and the rank-1 switches agree with the curve.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

TAGS = ["DE_CH", "FR_CH", "national"]
CONSISTENCY_ATOL = 1e-12
LINEARITY_ATOL = 1e-9


def _numbers(entries):
    return [float(e) for e in entries if not isinstance(e, str)]


def _group(curve, tag):
    return curve[curve["region"] == tag]


def test_curve_complete(cost_scale_curve_regional, cost_scale_factors, rankings_regional):
    curve = cost_scale_curve_regional
    labels = [e if isinstance(e, str) else str(float(e)) for e in cost_scale_factors]
    assert list(curve["cost_scale_label"].drop_duplicates()) == labels
    assert curve.groupby("cost_scale_label")["cost_scale_factor"].nunique().eq(1).all()
    n = len(rankings_regional)
    assert len(curve) == len(cost_scale_factors) * len(TAGS) * n
    for (_, _), g in curve.groupby(["cost_scale_label", "region"]):
        assert sorted(g["rank"]) == list(range(1, n + 1))
        assert abs(g["p_rank1"].sum() - 1) < 1e-9


@pytest.mark.parametrize("tag", TAGS)
def test_curve_reproduces_main_ranking(cost_scale_curve_regional, rankings_regional, cost_scale, cost_scale_factors,
                                       tag):
    """At the factor of the main analysis (price.cost_scale_factor) the sweep must equal utility_rankings_regional."""
    if float(cost_scale) not in _numbers(cost_scale_factors):
        pytest.skip(f"price.cost_scale_factor {cost_scale} is not among the sensitivity factors")
    curve = _group(cost_scale_curve_regional, tag)
    point = curve[curve["cost_scale_label"] == str(float(cost_scale))].set_index("scenario_id").loc[rankings_regional["scenario_id"]]
    main = rankings_regional.set_index("scenario_id")
    assert (point["rank"] == main[f"rank_{tag}"]).all()
    assert np.abs(point["p_rank1"] - main[f"p_rank1_{tag}"]).max() < CONSISTENCY_ATOL
    assert np.abs(point["utility"] - main[f"utility_{tag}"]).max() < CONSISTENCY_ATOL
    for end in ("low", "high"):
        main_column = next(c for c in main.columns if c.startswith(f"utility_{tag}_") and c.endswith(f"_{end}"))
        assert np.abs(point[f"utility_interval_{end}"] - main[main_column]).max() < CONSISTENCY_ATOL


def test_conversion_factors(cost_scale_curve_regional, cost_scale_factors, cost_scale_conversions, eur_to_chf):
    """Each named entry is evaluated with the factor of its conversion, from the inputs in the config and the
    pipeline's EUR/CHF rate (hicp: index ratio; chf_lik: EUR/CHF of the base year x Swiss CPI ratio / EUR/CHF)."""
    named = [e for e in cost_scale_factors if isinstance(e, str)]
    factor = cost_scale_curve_regional.drop_duplicates("cost_scale_label").set_index("cost_scale_label")["cost_scale_factor"]
    for name in named:
        c = cost_scale_conversions[name]
        expected = (c["index_to"] / c["index_from"] if c["method"] == "hicp"
                    else c["eur_chf_from"] * c["lik_to"] / c["lik_from"] / eur_to_chf)
        assert abs(factor[name] - expected) < CONSISTENCY_ATOL, name


def test_conversion_factors_in_search_range(cost_scale_curve_regional, cost_scale_search):
    """The rank-1 switches are searched over a range that contains every evaluated factor."""
    f = cost_scale_curve_regional["cost_scale_factor"]
    assert cost_scale_search["start"] <= f.min() and f.max() <= cost_scale_search["stop"]


@pytest.mark.parametrize("tag", TAGS)
def test_utility_linear_and_decreasing_in_factor(cost_scale_curve_regional, tag):
    """The price change is linear in the system cost and the utility linear in the price change, so the utility of
    every scenario is linear in the factor; with C_s > 0 and a negative price coefficient it falls as the factor rises."""
    u = _group(cost_scale_curve_regional, tag).pivot(index="cost_scale_factor", columns="scenario_id", values="utility")
    if len(u) < 3:
        pytest.skip("linearity needs at least three factors")
    k = u.index.to_numpy()
    slope = (u.iloc[-1] - u.iloc[0]) / (k[-1] - k[0])
    predicted = u.iloc[0].to_numpy() + np.outer(k - k[0], slope.to_numpy())
    assert np.abs(u.to_numpy() - predicted).max() < LINEARITY_ATOL
    assert (np.diff(u.to_numpy(), axis=0) < 0).all()


def test_switches_are_rank1_changes(cost_scale_switches_regional, cost_scale_search):
    for _, s in cost_scale_switches_regional.iterrows():
        where = f"{s['region']} at {s['switch_cost_scale_factor']:.6f}"
        assert cost_scale_search["start"] <= s["switch_cost_scale_factor"] <= cost_scale_search["stop"], where
        assert s["scenario_before"] != s["scenario_after"], where
        assert s["rank1_below"] == s["scenario_before"] and s["rank1_above"] == s["scenario_after"], where


@pytest.mark.parametrize("tag", TAGS)
def test_switches_agree_with_curve(cost_scale_curve_regional, cost_scale_switches_regional, tag):
    """Rank 1 of the curve at every factor is the scenario the switches predict there."""
    switches = cost_scale_switches_regional[cost_scale_switches_regional["region"] == tag].sort_values(
        "switch_cost_scale_factor")
    curve = _group(cost_scale_curve_regional, tag)
    for factor, g in curve.groupby("cost_scale_factor"):
        leader = g.loc[g["rank"] == 1, "scenario_id"].item()
        before = switches[switches["switch_cost_scale_factor"] > factor]
        after = switches[switches["switch_cost_scale_factor"] <= factor]
        expected = (before["scenario_before"].iloc[0] if len(before)
                    else after["scenario_after"].iloc[-1] if len(after) else leader)
        assert leader == expected, f"{tag} at factor {factor}"
