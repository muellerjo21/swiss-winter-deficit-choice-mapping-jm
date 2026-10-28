"""Import attribute definitions (rule import_shares, src/load_data.import_quantities): electricity only (main),
+ natural gas, hydrogen and synthetic methane, + synthetic diesel. Annual sums at the Swiss locations divided by
the electricity consumption, clipped to [0, 1]. Assumption of the fuel variants: 1 GWh fuel = 1 GWh electricity.

Pytest fixtures are provided from within the test runner.
"""
import numpy as np
import pytest

DEFINITIONS = ["electricity", "electricity_fuels", "electricity_fuels_diesel"]
EXACT_ATOL = 1e-9
PERCENT_ATOL = 0.05 + 1e-9  # table values are rounded to 0.1 percentage points

# Import attribute in % per scenario: (electricity, + fuels, + fuels + synthetic diesel), annual, clipped to [0, 100]
EXPECTED_PERCENT = {
    "baseline": (12.4, 25.8, 34.4),
    "baseline_no_self_sufficiency_result_4H": (8.6, 20.1, 20.1),
    "policy_alpine_pv": (0.0, 0.0, 0.0),
    "policy_chp": (1.9, 23.9, 23.9),
    "policy_h2_imports_only": (16.5, 37.4, 37.4),
    "policy_mix": (13.6, 41.6, 41.6),
    "policy_remix": (1.9, 1.9, 1.9),
    "policy_roof_pv": (1.9, 15.3, 23.9),
    "policy_sccgt_daccs": (14.8, 47.7, 47.7),
    "policy_sccgt_no_h2": (7.5, 7.5, 7.5),
    "policy_sccgt_plus_h2": (7.5, 7.5, 7.5),
    "policy_wind_x2": (0.6, 14.7, 21.8),
}
VARIANTS = {"electricity_fuels": "import: electricity + fuels (year)",
            "electricity_fuels_diesel": "import: electricity + fuels + synthetic diesel (year)"}


@pytest.mark.parametrize("scenario", sorted(EXPECTED_PERCENT))
def test_import_shares_as_in_table(import_shares, scenario):
    row = import_shares.set_index("scenario_id").loc[scenario]
    for definition, expected in zip(DEFINITIONS, EXPECTED_PERCENT[scenario]):
        assert abs(100 * row[f"import_share_{definition}"] - expected) < PERCENT_ATOL, definition


def test_import_shares_regression(import_shares, reference_import_shares):
    assert list(import_shares.columns) == list(reference_import_shares.columns)
    assert list(import_shares["scenario_id"]) == list(reference_import_shares["scenario_id"])
    numeric = [c for c in import_shares.columns if c != "scenario_id"]
    assert np.abs(import_shares[numeric].to_numpy(float) - reference_import_shares[numeric].to_numpy(float)).max() < EXACT_ATOL


def test_main_analysis_uses_configured_definition(import_shares, regional_attributes, import_definition):
    """The import_share of the regional main analysis equals the configured definition exactly (default
    electricity: byte-identical to the national electricity import share)."""
    expected = import_shares.set_index("scenario_id")[f"import_share_{import_definition}"]
    actual = regional_attributes.drop_duplicates("scenario_id").set_index("scenario_id")["import_share"]
    assert (actual == expected.loc[actual.index]).all()


def test_units_and_ordering(import_shares):
    """GWh: Swiss electricity consumption incl. sector coupling is 50-150 TWh/a; fuel imports are non-negative;
    each definition adds imports to the previous one (unclipped shares ordered)."""
    t = import_shares
    assert t["consumption_gwh"].between(50_000, 150_000).all()
    fuel_columns = [c for c in t.columns if c.startswith("import_") and c.endswith("_gwh")]
    assert len(fuel_columns) == 4 and (t[fuel_columns] >= 0).all().all()
    e, f, d = (t[f"import_share_{x}_unclipped"] for x in DEFINITIONS)
    assert (e <= f + EXACT_ATOL).all() and (f <= d + EXACT_ATOL).all()
    for x in DEFINITIONS:
        assert t[f"import_share_{x}"].between(0, 1).all()
        assert np.allclose(t[f"import_share_{x}"], t[f"import_share_{x}_unclipped"].clip(0, 1), rtol=0, atol=0)


@pytest.mark.parametrize("definition", sorted(VARIANTS))
def test_sensitivity_rows(sensitivities_regional, definition):
    rows = sensitivities_regional[sensitivities_regional["variant"] == VARIANTS[definition]]
    assert len(rows) == 12
    for tag in ["national", "DE_CH", "FR_CH"]:
        assert rows[f"p_rank1_{tag}"].between(0, 1).all()
        assert abs(rows[f"p_rank1_{tag}"].sum() - 1) < 1e-9
        assert sorted(rows[f"rank_{tag}"]) == list(range(1, 13))
