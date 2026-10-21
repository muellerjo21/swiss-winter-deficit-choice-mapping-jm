"""Tests of the reference-price sensitivity (rule sensitivity_reference_price, fig6): regression against
the frozen references in data/processed/ and graphics/, consistency with utility_rankings.csv and
plausibility of the crossing points.

Pytest fixtures are provided from within the test runner.
"""
from pathlib import Path

import numpy as np
import pytest

ATTRIBUTE_ATOL = 1e-9   # price_change, reference values, EUR/CHF: deterministic -> practically exact
UTILITY_ATOL = 0.005    # utility and P(rank 1), as in test_regression.py
CROSSING_ATOL = 1e-6    # crossing point (Rp./kWh); bisection tolerance is far below
CONSISTENCY_ATOL = 1e-12

CURVE_KEYS = ["total_rp_kwh", "scenario_id", "region"]
BASE_YEAR_KEYS = ["year", "scenario_id", "region"]


def _aligned(actual, expected, keys):
    a, e = actual.set_index(keys).sort_index(), expected.set_index(keys).sort_index()
    assert list(a.index) == list(e.index)
    return a, e


def test_curve_columns_and_points(sensitivity_curve, reference_sensitivity_curve):
    assert list(sensitivity_curve.columns) == list(reference_sensitivity_curve.columns)
    _aligned(sensitivity_curve, reference_sensitivity_curve, CURVE_KEYS)


def test_curve_values(sensitivity_curve, reference_sensitivity_curve):
    a, e = _aligned(sensitivity_curve, reference_sensitivity_curve, CURVE_KEYS)
    assert (a["rank"] == e["rank"]).all()
    assert (a["is_reference_year"] == e["is_reference_year"]).all()
    assert np.abs(a[["p_rank1", "utility"]].to_numpy() - e[["p_rank1", "utility"]].to_numpy()).max() < UTILITY_ATOL


def test_crossings_regression(sensitivity_crossings, reference_sensitivity_crossings):
    a, e = sensitivity_crossings, reference_sensitivity_crossings
    assert list(a.columns) == list(e.columns) and list(a.index) == list(e.index)
    assert np.abs(a["crossing_rp_kwh"] - e["crossing_rp_kwh"]).max() < CROSSING_ATOL
    rank_cols = [c for c in a.columns if c.startswith("rank_")]
    assert (a[rank_cols] == e[rank_cols]).all().all()


def test_base_years_regression(sensitivity_base_years, reference_sensitivity_base_years):
    assert list(sensitivity_base_years.columns) == list(reference_sensitivity_base_years.columns)
    a, e = _aligned(sensitivity_base_years, reference_sensitivity_base_years, BASE_YEAR_KEYS)
    exact = ["total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh", "eur_to_chf", "price_change"]
    assert np.abs(a[exact].to_numpy() - e[exact].to_numpy()).max() < ATTRIBUTE_ATOL
    assert (a[["n_days", "rank"]] == e[["n_days", "rank"]]).all().all()
    assert np.abs(a[["p_rank1", "utility"]].to_numpy() - e[["p_rank1", "utility"]].to_numpy()).max() < UTILITY_ATOL


@pytest.mark.parametrize("tag", ["DE_CH", "FR_CH", "national"])
def test_curve_reproduces_reference_rankings(sensitivity_curve, reference_rankings, tag):
    """At the reference year's own total_rp_kwh the curve must equal utility_rankings.csv."""
    point = sensitivity_curve[sensitivity_curve["is_reference_year"] & (sensitivity_curve["region"] == tag)]
    point = point.set_index("scenario_id").loc[reference_rankings.index]
    assert len(point) == len(reference_rankings)
    assert (point["rank"] == reference_rankings[f"rank_{tag}"]).all()
    assert np.abs(point["p_rank1"] - reference_rankings[f"p_rank1_{tag}"]).max() < CONSISTENCY_ATOL
    assert np.abs(point["utility"] - reference_rankings[f"utility_{tag}"]).max() < CONSISTENCY_ATOL


@pytest.mark.parametrize("tag", ["DE_CH", "FR_CH", "national"])
def test_crossing_in_range_and_ranks_swap(sensitivity_crossings, sensitivity_curve, tag):
    row = sensitivity_crossings.loc[tag]
    grid = sensitivity_curve[~sensitivity_curve["is_reference_year"]]
    assert grid["total_rp_kwh"].min() <= row["crossing_rp_kwh"] <= grid["total_rp_kwh"].max()
    # ranks just below and above the crossing point have the opposite order
    assert np.sign(row["rank_a_below"] - row["rank_b_below"]) == -np.sign(row["rank_a_above"] - row["rank_b_above"]) != 0
    # same on the curve: last grid point below and first grid point above
    region = grid[grid["region"] == tag].pivot(index="total_rp_kwh", columns="scenario_id", values="rank")
    below = region.loc[region.index[region.index < row["crossing_rp_kwh"]].max()]
    above = region.loc[region.index[region.index > row["crossing_rp_kwh"]].min()]
    a, b = row["scenario_a"], row["scenario_b"]
    assert np.sign(below[a] - below[b]) == -np.sign(above[a] - above[b]) != 0


def test_figure_identical_to_reference(figure_sensitivity_pairs):
    """fig6 PNG and PDF are byte-reproducible (no timestamps) -> compare with graphics/."""
    for built, reference in figure_sensitivity_pairs:
        assert Path(built).read_bytes() == Path(reference).read_bytes(), built
