"""Creates the pairwise choice probability matrix (fig9, as in Tröndle et al. 2025, Fig. 2/4)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from make_graphics import fig_pairwise_matrix, figure_settings


if __name__ == "__main__":
    p = snakemake.params
    attributes = pd.read_csv(snakemake.input.attributes)
    cost = attributes.drop_duplicates("scenario_id").set_index("scenario_id")["mellot_cost_change_pct"].reindex(p.scenario_ids)
    fig_pairwise_matrix(pd.read_csv(snakemake.input.matrix), figure_settings("regional", p, cost),
                        out_dir=Path(snakemake.output[0]).parent.parent, decimals=p.decimals, formats=p.formats)
