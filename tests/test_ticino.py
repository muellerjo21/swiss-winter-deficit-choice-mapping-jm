"""Tests of the Ticino switch (spatial.regional.ticino): TI included with the configured coefficients (or excluded),
population weights over all included regions sum to 1, TI counts towards Switzerland only, its utility equals the
utility of its coefficients with its own attributes, and the TI sensitivity with the main coefficients reproduces the
main analysis. The utility checks are computed in the rule regional_utility (the test environment has no access to
the choice model).

Pytest fixtures are provided from within the test runner.
"""
import numpy as np

CONSISTENCY_ATOL = 1e-12


def _regions(region_rankings_regional):
    return region_rankings_regional.drop_duplicates("region").set_index("region")


def test_regions_included(region_rankings_regional, ticino):
    regions = _regions(region_rankings_regional)
    assert len(regions) == (22 if ticino is None else 23)
    assert ("TI" in regions.index) == (ticino is not None)


def test_population_weights_sum_to_one(region_rankings_regional):
    assert abs(_regions(region_rankings_regional)["weight"].sum() - 1) < CONSISTENCY_ATOL


def test_ticino_coefficients_and_groups(region_rankings_regional, ticino):
    """TI uses the configured coefficients and belongs to no language group (DE-CH, FR-CH), only to Switzerland."""
    if ticino is None:
        return
    ti = _regions(region_rankings_regional).loc["TI"]
    assert ti["coefficients"] == ticino
    assert ti["language"] != ti["language"]  # NaN: no language region


def test_ticino_utility_check(regional_checks, ticino):
    """TI utility = utility of its coefficients with the TI attributes (national code path); row only with TI."""
    rows = regional_checks[regional_checks["check"].str.startswith("TI: utility")]
    assert len(rows) == (0 if ticino is None else 1)
    for _, row in rows.iterrows():
        assert f"= {ticino} utility" in row["check"]
        assert row["value"] <= row["tolerance"], row["check"]


def test_ticino_sensitivity_with_main_coefficients(sensitivities_regional, rankings_regional, ticino):
    """The variant 'TI with <main coefficients>' equals the main analysis; with TI excluded the variants keep their
    previous labels."""
    variants = set(sensitivities_regional["variant"])
    if ticino is None:
        assert {"excluded regions with DE-CH coefficients", "excluded regions with FR-CH coefficients",
                "excluded regions with mixed coefficients"} <= variants
        return
    assert {"TI with DE-CH coefficients", "TI with FR-CH coefficients", "TI with mixed coefficients"} <= variants
    variant = sensitivities_regional[sensitivities_regional["variant"] == f"TI with {ticino} coefficients"]
    variant = variant.set_index("scenario_id").loc[rankings_regional["scenario_id"]]
    main = rankings_regional.set_index("scenario_id")
    for column in [c for c in main.columns if c.startswith(("utility_", "p_rank1_"))]:
        assert np.abs(variant[column] - main[column]).max() < CONSISTENCY_ATOL, column
    for column in ["rank_DE_CH", "rank_FR_CH", "rank_national"]:
        assert (variant[column] == main[column]).all(), column


def test_ticino_variants_identical_with_one_swiss_coefficient_set(sensitivities_regional, choice_model_coefficients,
                                                                  ticino):
    """With a choice model that has one coefficient set for Switzerland (DE-CH and FR-CH mapped to the same country,
    e.g. the measured model), the TI variants with DE-CH, FR-CH and mixed coefficients give identical results
    (mixed = language-weighted sum of the same coefficients, equal up to rounding)."""
    if ticino is None or len(set(choice_model_coefficients.values())) > 1:
        return
    variants = [f"TI with {c} coefficients" for c in ("DE-CH", "FR-CH", "mixed")]
    tables = [sensitivities_regional[sensitivities_regional["variant"] == v].set_index("scenario_id").sort_index()
              for v in variants]
    columns = [c for c in tables[0].columns if c.startswith(("utility_", "p_rank1_"))]
    for other in tables[1:]:
        assert np.abs(other[columns] - tables[0][columns]).to_numpy().max() < CONSISTENCY_ATOL
        ranks = ["rank_DE_CH", "rank_FR_CH", "rank_national"]
        assert (other[ranks] == tables[0][ranks]).all().all()
