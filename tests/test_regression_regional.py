"""Regression test of the regional main analysis (rules regional_attributes, regional_utility,
regional_reference_price) against the frozen references in data/processed/ (*_regional.csv), plus consistency
of the reference-price curve with the main ranking. Tolerances as in test_regression.py / test_sensitivity.py.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

ATTRIBUTE_ATOL = 1e-9   # attributes, weights, population shares: deterministic -> practically exact
UTILITY_ATOL = 0.005    # utility, CI and P(rank 1)
SWITCH_ATOL = 1e-6      # switch point (Rp./kWh shift); bisection tolerance is far below
CONSISTENCY_ATOL = 1e-12


def _interval_tag(table):
    """Tag of the interval columns (utility_national_<tag>_low), e.g. hdi96; set by the config."""
    tags = {c[len("utility_national_"):-len("_low")] for c in table.columns
            if c.startswith("utility_national_") and c.endswith("_low")}
    assert len(tags) == 1, tags
    return tags.pop()

TAGS = ["DE_CH", "FR_CH", "national"]
ATTRIBUTE_COLUMNS = [
    "relative_land", "import_share", "ownership_commercial", "ownership_community", "ownership_public",
    "source_wind", "source_gas", "source_biomass", "source_coal", "source_nuclear",
    "transmission_change", "price_change", "relative_land_national", "import_share_balance",
]


def _aligned(actual, expected, keys):
    assert list(actual.columns) == list(expected.columns)
    a, e = actual.set_index(keys).sort_index(), expected.set_index(keys).sort_index()
    assert list(a.index) == list(e.index)
    return a, e


def _max_abs_diff(a, e, columns):
    return np.nanmax(np.abs(a[columns].to_numpy(float) - e[columns].to_numpy(float)))


def _ranking_columns(tag, ci):
    return [f"utility_{tag}", f"utility_{tag}_{ci}_low", f"utility_{tag}_{ci}_high", f"p_rank1_{tag}"]


def test_regional_attributes_keys(regional_attributes, reference_regional_attributes):
    a, e = _aligned(regional_attributes, reference_regional_attributes, ["scenario_id", "region"])
    assert (a["language"].fillna("") == e["language"].fillna("")).all()


@pytest.mark.parametrize("column", ATTRIBUTE_COLUMNS + ["mellot_cost_change_pct"])
def test_regional_attribute_values(regional_attributes, reference_regional_attributes, column):
    a, e = _aligned(regional_attributes, reference_regional_attributes, ["scenario_id", "region"])
    assert _max_abs_diff(a, e, [column]) < ATTRIBUTE_ATOL


def test_rankings_regional_order(rankings_regional, reference_rankings_regional):
    assert list(rankings_regional.columns) == list(reference_rankings_regional.columns)
    assert list(rankings_regional["scenario_id"]) == list(reference_rankings_regional["scenario_id"])


@pytest.mark.parametrize("tag", TAGS)
def test_rankings_regional_values(rankings_regional, reference_rankings_regional, tag):
    a, e = _aligned(rankings_regional, reference_rankings_regional, ["scenario_id"])
    assert _max_abs_diff(a, e, _ranking_columns(tag, _interval_tag(a))) < UTILITY_ATOL
    assert (a[f"rank_{tag}"] == e[f"rank_{tag}"]).all()


def test_rankings_regional_cost_ranks(rankings_regional, reference_rankings_regional):
    a, e = _aligned(rankings_regional, reference_rankings_regional, ["scenario_id"])
    for c in ["rank_mellot_cost", "rank_diff_national_vs_mellot"]:
        assert ((a[c] == e[c]) | (a[c].isna() & e[c].isna())).all(), c


def test_region_rankings(region_rankings_regional, reference_region_rankings_regional):
    a, e = _aligned(region_rankings_regional, reference_region_rankings_regional, ["region", "scenario_id"])
    for c in ["language", "coefficients"]:
        assert (a[c].fillna("") == e[c].fillna("")).all(), c
    assert (a["population"] == e["population"]).all()
    assert (a["rank"] == e["rank"]).all()
    assert _max_abs_diff(a, e, ["weight"]) < ATTRIBUTE_ATOL
    assert _max_abs_diff(a, e, ["utility", "p_rank1"]) < UTILITY_ATOL


def test_rank1_population_share(rank1_share_regional, reference_rank1_share_regional):
    a, e = _aligned(rank1_share_regional, reference_rank1_share_regional, ["scenario_id"])
    assert _max_abs_diff(a, e, ["population_share_rank1"]) < ATTRIBUTE_ATOL


@pytest.mark.parametrize("tag", TAGS)
def test_sensitivities_regional(sensitivities_regional, reference_sensitivities_regional, tag):
    a, e = _aligned(sensitivities_regional, reference_sensitivities_regional, ["variant", "scenario_id"])
    assert _max_abs_diff(a, e, _ranking_columns(tag, _interval_tag(a))) < UTILITY_ATOL
    assert (a[f"rank_{tag}"] == e[f"rank_{tag}"]).all()


def test_sensitivities_main_is_main_ranking(sensitivities_regional, rankings_regional):
    main = sensitivities_regional[sensitivities_regional["variant"] == "main"].drop(columns="variant")
    assert main.reset_index(drop=True).equals(rankings_regional.reset_index(drop=True))


def test_curve_regional(sensitivity_curve_regional, reference_sensitivity_curve_regional):
    a, e = _aligned(sensitivity_curve_regional, reference_sensitivity_curve_regional,
                    ["shift_rp_kwh", "region", "scenario_id"])
    assert (a["rank"] == e["rank"]).all()
    assert (a["is_reference_year"] == e["is_reference_year"]).all()
    assert _max_abs_diff(a, e, ["p_rank1", "utility"]) < UTILITY_ATOL


@pytest.mark.parametrize("tag", TAGS)
def test_curve_regional_reproduces_main_ranking(sensitivity_curve_regional, rankings_regional, tag):
    """At shift 0 (the reference year's own prices) the curve must equal utility_rankings_regional.csv."""
    point = sensitivity_curve_regional[sensitivity_curve_regional["is_reference_year"]
                                       & (sensitivity_curve_regional["region"] == tag)]
    assert (point["shift_rp_kwh"] == 0).all()
    point = point.set_index("scenario_id").loc[rankings_regional["scenario_id"]]
    main = rankings_regional.set_index("scenario_id")
    assert (point["rank"] == main[f"rank_{tag}"]).all()
    assert np.abs(point["p_rank1"] - main[f"p_rank1_{tag}"]).max() < CONSISTENCY_ATOL
    assert np.abs(point["utility"] - main[f"utility_{tag}"]).max() < CONSISTENCY_ATOL


def test_switches_regional(sensitivity_switches_regional, reference_sensitivity_switches_regional):
    a, e = sensitivity_switches_regional, reference_sensitivity_switches_regional
    assert list(a.columns) == list(e.columns)
    keys = ["region", "scenario_before", "scenario_after", "rank1_below", "rank1_above"]
    assert a[keys].values.tolist() == e[keys].values.tolist()
    assert np.abs(a["switch_shift_rp_kwh"] - e["switch_shift_rp_kwh"]).max() < SWITCH_ATOL


def test_switches_regional_are_rank1_changes(sensitivity_switches_regional, sensitivity_curve_regional):
    """Every switch lies inside the swept range and swaps rank 1 from 'before' to 'after'."""
    grid = sensitivity_curve_regional[~sensitivity_curve_regional["is_reference_year"]]
    for _, s in sensitivity_switches_regional.iterrows():
        where = f"{s['region']} at {s['switch_shift_rp_kwh']:.4f}"
        assert grid["shift_rp_kwh"].min() <= s["switch_shift_rp_kwh"] <= grid["shift_rp_kwh"].max(), where
        assert s["scenario_before"] != s["scenario_after"], where
        assert s["rank1_below"] == s["scenario_before"] and s["rank1_above"] == s["scenario_after"], where
