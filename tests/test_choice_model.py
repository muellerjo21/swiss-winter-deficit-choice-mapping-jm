"""Tests of the choice model (data.choice_model): the Swiss coefficients the pipeline loads equal the model's own
variables draw by draw (per-group partworths, or the European mean beta_partworths plus the country effect
effect_country), and recompute the model's utility u_right of the Swiss choice situations. Computed in the rule
beta_real_units (choice_model_check.csv; the test environment has no access to the choice model).

Pytest fixtures are provided from within the test runner.
"""
CONSISTENCY_ATOL = 1e-12


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
