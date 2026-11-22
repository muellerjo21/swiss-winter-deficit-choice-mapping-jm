"""Tests of the choice model (data.choice_model): the Swiss coefficients the pipeline loads equal the model's own
variables draw by draw (per-group partworths, or the European mean beta_partworths plus the country effect
effect_country), and recompute the model's utility u_right of the Swiss choice situations. Computed in the rule
beta_real_units (choice_model_check.csv; the test environment has no access to the choice model).

Pytest fixtures are provided from within the test runner.
"""
import pandas as pd

CONSISTENCY_ATOL = 1e-12
TICINO = "TI"  # the region without a language group of its own (spatial.regional.ticino)


def test_swiss_groups_mapped_as_configured(choice_model_check, choice_model_coefficients):
    check = choice_model_check.set_index("group")
    assert sorted(check.index) == sorted(choice_model_coefficients)
    for group, country in choice_model_coefficients.items():
        assert check.loc[group, "model_country"] == country


def test_coefficients_equal_model_variables_draw_by_draw(choice_model_check):
    assert (choice_model_check["n_samples"] > 0).all()
    assert (choice_model_check["max_abs_diff_samples"] < CONSISTENCY_ATOL).all()


def test_coefficients_reproduce_model_utility(choice_model_check):
    assert (choice_model_check["n_situations"] > 0).all()
    assert (choice_model_check["max_abs_diff_u_right"] < CONSISTENCY_ATOL).all()


def test_regions_get_the_coefficients_of_their_language_group(region_rankings_regional, choice_model_coefficients):
    """Every region of a language group (regions.language) is computed with that group's coefficients; the groups are
    the ones mapped to the model (data.choice_models.<entry>.coefficients)."""
    regions = region_rankings_regional.drop_duplicates("region").set_index("region")
    with_language = regions[regions["language"].notna()]
    assert set(with_language["language"]) == set(choice_model_coefficients)
    assert (with_language["coefficients"] == with_language["language"]).all(), with_language[["language", "coefficients"]]


def test_ticino_gets_the_configured_coefficients(region_rankings_regional, ticino):
    regions = region_rankings_regional.drop_duplicates("region").set_index("region")
    if ticino is None:
        assert TICINO not in regions.index
    else:
        assert regions.loc[TICINO, "coefficients"] == ticino and pd.isna(regions.loc[TICINO, "language"])


def test_language_groups_map_to_distinct_model_groups_or_one_swiss_set(choice_model_check):
    """Either each language group has its own group in the model file, or both use one Swiss set."""
    countries = choice_model_check.set_index("group")["model_country"]
    assert countries.nunique() in (1, len(countries))
