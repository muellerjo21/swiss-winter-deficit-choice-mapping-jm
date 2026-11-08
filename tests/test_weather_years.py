"""Tests of the weather years (rules weather_year_rankings, weather_year_summary): the weather year of the main analysis
reproduces the main ranking, every year ranks exactly the scenarios with a result file, the common set is the same in
every year, and the missing runs are the complement; regression of the comparison table, the missing runs and the
regional attributes of every year against the frozen references in data/processed/weather/.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np

CONSISTENCY_ATOL = 1e-12
ATTRIBUTE_ATOL = 1e-9   # attributes are deterministic, as in test_regression.py
UTILITY_ATOL = 0.005    # utility, credible interval and P(rank 1), as in test_regression.py
SUMMARY_KEYS = ["weather_year", "scenario_set", "group", "scenario_id"]


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


def test_weather_rankings_regression(weather_summary, reference_weather_rankings):
    assert list(weather_summary.columns) == list(reference_weather_rankings.columns)
    a = weather_summary.set_index(SUMMARY_KEYS).sort_index()
    e = reference_weather_rankings.set_index(SUMMARY_KEYS).sort_index()
    assert list(a.index) == list(e.index)
    assert (a[["rank", "n_scenarios"]] == e[["rank", "n_scenarios"]]).all().all()
    columns = ["p_rank1", "utility", "utility_interval_low", "utility_interval_high"]
    assert np.abs(a[columns].to_numpy() - e[columns].to_numpy()).max() < UTILITY_ATOL


def test_missing_runs_regression(weather_missing, reference_weather_missing_runs):
    assert weather_missing.values.tolist() == reference_weather_missing_runs.values.tolist()


def test_weather_regional_attributes_regression(weather_regional_attributes, reference_weather_regional_attributes):
    for year, actual in weather_regional_attributes.items():
        expected = reference_weather_regional_attributes[year]
        assert list(actual.columns) == list(expected.columns), year
        keys = ["scenario_id", "region"]
        a, e = actual.set_index(keys).sort_index(), expected.set_index(keys).sort_index()
        assert list(a.index) == list(e.index), year
        numeric = list(a.select_dtypes("number").columns)
        assert np.nanmax(np.abs(a[numeric].to_numpy(float) - e[numeric].to_numpy(float))) < ATTRIBUTE_ATOL, year
        assert (a["language"].fillna("") == e["language"].fillna("")).all(), year
