"""Maps of the regional choice probability per map pair (fig10, as in Tröndle et al. 2025, Fig. 1/3), each with
the full colour range and the narrowed variant, and the check that every region of the analysis matches exactly
one geometry. Runs in envs/maps.yaml."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from maps import fig_choice_map, geometry_checks, load_region_geometries
from plot_style import FigureSettings


if __name__ == "__main__":
    p = snakemake.params
    b = p.boundaries
    geometries = load_region_geometries(snakemake.input.boundaries, b["member"], b["layer"], p.crs, p.tolerance)
    regions = pd.read_csv(snakemake.input.population)["region"].tolist()
    geometry_checks(geometries, regions).to_csv(snakemake.output.checks, index=False)
    fs = FigureSettings("regional", p.credible_interval, p.interval_type, p.year)
    for path, names in zip(snakemake.input.tables, p.names):
        table = pd.read_csv(path)
        for name, color_range in zip(names, p.color_ranges):
            fig_choice_map(geometries, table, p.exclude, fs, Path(p.figure_dir), name, color_range, p.formats)
