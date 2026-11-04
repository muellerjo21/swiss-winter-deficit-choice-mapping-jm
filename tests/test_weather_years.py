"""Tests of the weather years (rules weather_year_rankings, weather_year_summary): the weather year of the main analysis
reproduces the main ranking, every year ranks exactly the scenarios with a result file, the common set is the same in
every year, and the missing runs are the complement.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np

CONSISTENCY_ATOL = 1e-12


def test_main_weather_year_reproduces_main_analysis(weather_rankings_main, rankings_regional):
    a = weather_rankings_main.set_index("scenario_id").loc[rankings_regional["scenario_id"]]
    main = rankings_regional.set_index("scenario_id")
    for column in [c for c in main.columns if c.startswith(("utility_", "p_rank1_"))]:
        assert np.abs(a[column] - main[column]).max() < CONSISTENCY_ATOL, column
    for column in ["rank_DE_CH", "rank_FR_CH", "rank_national"]:
        assert (a[column] == main[column]).all(), column


def test_scenarios_per_year(weather_summary, weather_years, weather_scenarios, common_scenarios):
    for year in weather_years:
        for scenario_set, expected in [("all", weather_scenarios[year]), ("common", common_scenarios)]:
            t = weather_summary[(weather_summary["weather_year"] == year) & (weather_summary["scenario_set"] == scenario_set)]
            for group, g in t.groupby("group"):
                where = f"{year} {scenario_set} {group}"
                assert sorted(g["scenario_id"]) == sorted(expected), where
                assert sorted(g["rank"]) == list(range(1, len(expected) + 1)), where
                assert abs(g["p_rank1"].sum() - 1) < 1e-9, where
                assert (g["n_scenarios"] == len(expected)).all(), where
                assert (g["utility_interval_low"] <= g["utility"]).all() and (g["utility"] <= g["utility_interval_high"]).all(), where


def test_common_scenarios_in_every_year(weather_scenarios, common_scenarios):
    assert common_scenarios
    for year, scenarios in weather_scenarios.items():
        assert set(common_scenarios) <= set(scenarios), year


def test_missing_runs(weather_missing, weather_years, weather_scenarios):
    available = {(y, s) for y in weather_years for s in weather_scenarios[y]}
    missing = set(zip(weather_missing["weather_year"], weather_missing["scenario_id"]))
    assert not available & missing
    all_ids = {s for y in weather_years for s in weather_scenarios[y]} | {s for _, s in missing}
    assert available | missing == {(y, s) for y in weather_years for s in all_ids}
