"""Creates fig6 of the national aggregate (P(rank 1) vs. ElCom reference price, base years)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from make_graphics import fig_reference_price_sensitivity, figure_settings


if __name__ == "__main__":
    fig_reference_price_sensitivity(
        curve=pd.read_csv(snakemake.input.curve),
        crossings=pd.read_csv(snakemake.input.crossings),
        base_years=pd.read_csv(snakemake.input.base_years),
        switches=pd.read_csv(snakemake.input.switches),
        fs=figure_settings("national", snakemake.params),
        out_dir=Path(snakemake.output[0]).parent.parent,
    )
