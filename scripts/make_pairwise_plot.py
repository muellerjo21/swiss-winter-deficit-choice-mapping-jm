"""Creates the pairwise choice probability matrix (fig9, as in Tröndle et al. 2025, Fig. 2/4)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from make_graphics import fig_pairwise_matrix, pairwise_order_note


if __name__ == "__main__":
    p = snakemake.params
    matrix = pd.read_csv(snakemake.input.matrix)
    attributes = pd.read_csv(snakemake.input.attributes)
    cost = attributes.drop_duplicates("scenario_id").set_index("scenario_id")["mellot_cost_change_pct"]
    order = matrix.sort_values("row").drop_duplicates("row")["scenario_1"].tolist()
    fig_pairwise_matrix(matrix, p.credible_interval, out_dir=Path(snakemake.output[0]).parent.parent,
                        order_note=pairwise_order_note(order, cost, not p.order), decimals=p.decimals,
                        name=p.name, formats=p.formats)
