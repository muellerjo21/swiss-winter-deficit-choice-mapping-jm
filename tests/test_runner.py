import sys
from pathlib import Path

import pandas as pd
import pytest


def run_test(snakemake):
    exit_code = pytest.main(
        [
            snakemake.input.test_dir,
            f"--html={snakemake.log[0]}",
            "--self-contained-html",
            "--verbose"
        ],
        plugins=[
            _create_config_plugin(snakemake=snakemake)
        ]
    )
    if exit_code == 0:
        Path(snakemake.output[0]).touch()
    sys.exit(exit_code)


def _create_config_plugin(snakemake):
    """Creates fixtures from Snakemake configuration."""

    class SnakemakeConfigPlugin():

        @pytest.fixture()
        def attributes(self):
            return pd.read_csv(snakemake.input.attributes).set_index("scenario_id")

        @pytest.fixture()
        def reference_attributes(self):
            return pd.read_csv(snakemake.input.reference_attributes).set_index("scenario_id")

        @pytest.fixture()
        def rankings(self):
            return pd.read_csv(snakemake.input.rankings).set_index("scenario_id")

        @pytest.fixture()
        def reference_rankings(self):
            return pd.read_csv(snakemake.input.reference_rankings).set_index("scenario_id")

        @pytest.fixture()
        def beta_real_units(self):
            return pd.read_csv(snakemake.input.beta_real_units)

        @pytest.fixture()
        def regional_attributes(self):
            return pd.read_csv(snakemake.input.regional_attributes)

        @pytest.fixture()
        def regional_checks(self):
            return pd.read_csv(snakemake.input.regional_checks)

        @pytest.fixture()
        def rankings_regional(self):
            return pd.read_csv(snakemake.input.rankings_regional)

        @pytest.fixture()
        def region_rankings_regional(self):
            return pd.read_csv(snakemake.input.region_rankings_regional)

        @pytest.fixture()
        def rank1_share_regional(self):
            return pd.read_csv(snakemake.input.rank1_share_regional)

        @pytest.fixture()
        def sensitivities_regional(self):
            return pd.read_csv(snakemake.input.sensitivities_regional)

        @pytest.fixture()
        def sensitivity_curve_regional(self):
            return pd.read_csv(snakemake.input.sensitivity_curve_regional)

        @pytest.fixture()
        def sensitivity_switches_regional(self):
            return pd.read_csv(snakemake.input.sensitivity_switches_regional)

        @pytest.fixture()
        def reference_rankings_regional(self):
            return pd.read_csv(snakemake.input.reference_rankings_regional)

        @pytest.fixture()
        def reference_region_rankings_regional(self):
            return pd.read_csv(snakemake.input.reference_region_rankings_regional)

        @pytest.fixture()
        def reference_rank1_share_regional(self):
            return pd.read_csv(snakemake.input.reference_rank1_share_regional)

        @pytest.fixture()
        def reference_sensitivities_regional(self):
            return pd.read_csv(snakemake.input.reference_sensitivities_regional)

        @pytest.fixture()
        def reference_sensitivity_curve_regional(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_curve_regional)

        @pytest.fixture()
        def reference_sensitivity_switches_regional(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_switches_regional)

        @pytest.fixture()
        def reference_regional_attributes(self):
            return pd.read_csv(snakemake.input.reference_regional_attributes)

        @pytest.fixture()
        def pairwise_matrix(self):
            return pd.read_csv(snakemake.input.pairwise_matrix)

        @pytest.fixture()
        def pairwise_regions(self):
            return pd.read_csv(snakemake.input.pairwise_regions)

        @pytest.fixture()
        def pairwise_map_tables(self):
            return [pd.read_csv(path) for path in snakemake.input.pairwise_map_tables]

        @pytest.fixture()
        def pairwise_checks(self):
            return pd.read_csv(snakemake.input.pairwise_checks)

        @pytest.fixture()
        def contributions_national(self):
            return pd.read_csv(snakemake.input.contributions_national)

        @pytest.fixture()
        def contributions_regional(self):
            return pd.read_csv(snakemake.input.contributions_regional)

        @pytest.fixture()
        def population_by_region(self):
            return pd.read_csv(snakemake.input.population_by_region)

        @pytest.fixture()
        def elcom_by_region(self):
            return pd.read_csv(snakemake.input.elcom_by_region)

        @pytest.fixture()
        def aggregation_comparison_regional(self):
            return pd.read_csv(snakemake.input.aggregation_comparison_regional)

        @pytest.fixture()
        def reference_population_by_region(self):
            return pd.read_csv(snakemake.input.reference_population_by_region)

        @pytest.fixture()
        def reference_elcom_by_region(self):
            return pd.read_csv(snakemake.input.reference_elcom_by_region)

        @pytest.fixture()
        def reference_pairwise_matrix_regional(self):
            return pd.read_csv(snakemake.input.reference_pairwise_matrix_regional)

        @pytest.fixture()
        def reference_pairwise_regions_regional(self):
            return pd.read_csv(snakemake.input.reference_pairwise_regions_regional)

        @pytest.fixture()
        def reference_aggregation_comparison_regional(self):
            return pd.read_csv(snakemake.input.reference_aggregation_comparison_regional)

        @pytest.fixture()
        def reference_contributions_regional(self):
            return pd.read_csv(snakemake.input.reference_contributions_regional)

        @pytest.fixture()
        def reference_contributions_national(self):
            return pd.read_csv(snakemake.input.reference_contributions_national)

        @pytest.fixture()
        def import_shares(self):
            return pd.read_csv(snakemake.input.import_shares_regional)

        @pytest.fixture()
        def reference_import_shares(self):
            return pd.read_csv(snakemake.input.reference_import_shares_regional)

        @pytest.fixture()
        def import_definition(self):
            return snakemake.params.import_definition

        @pytest.fixture()
        def geometry_checks(self):
            return pd.read_csv(snakemake.input.geometry_checks)

        @pytest.fixture()
        def sensitivity_curve(self):
            return pd.read_csv(snakemake.input.sensitivity_curve)

        @pytest.fixture()
        def reference_sensitivity_curve(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_curve)

        @pytest.fixture()
        def sensitivity_crossings(self):
            return pd.read_csv(snakemake.input.sensitivity_crossings).set_index("region")

        @pytest.fixture()
        def reference_sensitivity_crossings(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_crossings).set_index("region")

        @pytest.fixture()
        def sensitivity_base_years(self):
            return pd.read_csv(snakemake.input.sensitivity_base_years)

        @pytest.fixture()
        def reference_sensitivity_base_years(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_base_years)

        @pytest.fixture()
        def sensitivity_switches(self):
            return pd.read_csv(snakemake.input.sensitivity_switches)

        @pytest.fixture()
        def reference_sensitivity_switches(self):
            return pd.read_csv(snakemake.input.reference_sensitivity_switches)

        @pytest.fixture()
        def figure_sensitivity_pairs(self):
            """(build file, frozen reference file) per format."""
            return list(zip(snakemake.input.figure_sensitivity, snakemake.input.reference_figure_sensitivity))

    return SnakemakeConfigPlugin()


if __name__ == "__main__":
    run_test(snakemake)
