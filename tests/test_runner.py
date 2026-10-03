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

    return SnakemakeConfigPlugin()


if __name__ == "__main__":
    run_test(snakemake)
