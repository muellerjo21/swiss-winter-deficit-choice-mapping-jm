"""Language map (fig12): majority main language per canton with the language border (BFS) next to the coefficient
group of every Calliope region in this project. Figure only. Runs in envs/maps.yaml."""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from language_map import fig_language_map, language_borders, load_cantons


if __name__ == "__main__":
    p = snakemake.params
    b = p.boundaries
    cantons = load_cantons(snakemake.input.boundaries, b["member"], b["layer"], p.crs, p.tolerance)
    borders = language_borders(snakemake.input.boundaries, b["member"], p.areas["municipality_layer"], p.crs,
                               p.tolerance, pd.read_csv(snakemake.input.municipalities))
    release = re.search(r"swissboundaries3d_(\d{4}-\d{2})", b["url"]).group(1)
    out_dir = Path(snakemake.output.figures[0]).parent.parent  # build/figures (one subfolder per format)
    fig_language_map(cantons, pd.read_csv(snakemake.input.cantons), borders, p.languages, p.areas, p.ticino,
                     p.choice_model, p.coefficients, release, out_dir, p.name, p.formats)
