"""Maps of the regional choice probability per map pair (fig10, as in Tröndle et al. 2025, Fig. 1/3) and the check
that every region of the analysis matches exactly one geometry. Runs in envs/maps.yaml."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from maps import fig_choice_map, geometry_checks, load_region_geometries


if __name__ == "__main__":
    p = snakemake.params
    b = p.boundaries
    geometries = load_region_geometries(snakemake.input.boundaries, b["member"], b["layer"], p.crs, p.tolerance)
    regions = pd.read_csv(snakemake.input.population)["region"].tolist()
    geometry_checks(geometries, regions).to_csv(snakemake.output.checks, index=False)
    out_dir = Path(p.figure_dir)
    for path, name in zip(snakemake.input.tables, p.names):
        fig_choice_map(geometries, pd.read_csv(path), p.exclude, p.credible_interval, p.interval_type, out_dir, name,
                       p.formats)
