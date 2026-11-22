"""Regional reference values per Calliope region (src/regional.py): ElCom reference values (medians over the tariff
rows of the region's municipalities) and the permanent resident population. Separate from the attributes, so that
runs with other price settings or another weather year do not rewrite them."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from regional import municipality_regions, regional_elcom_reference, regional_population


if __name__ == "__main__":
    regions = municipality_regions(pd.read_csv(snakemake.input.cantons), snakemake.params.overrides)
    regional_elcom_reference(pd.read_csv(snakemake.input.prices), regions).rename_axis("region").to_csv(snakemake.output.elcom)
    regional_population(pd.read_csv(snakemake.input.statpop), regions).rename_axis("region").to_csv(snakemake.output.population)
