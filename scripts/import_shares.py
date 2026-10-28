"""Import attribute per scenario for the three definitions (src/load_data.import_quantities): net electricity
import, + natural gas, hydrogen and synthetic methane, + synthetic diesel; annual sums, clipped to [0, 1].
Fuels count with their energy content (1 GWh fuel = 1 GWh electricity)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import import_quantities


if __name__ == "__main__":
    p = snakemake.params
    rows = [{"scenario_id": s, **import_quantities(nc, p.fuel_techs, p.diesel_techs)}
            for s, nc in zip(p.scenario_ids, snakemake.input.nc)]
    pd.DataFrame(rows).to_csv(snakemake.output[0], index=False)
