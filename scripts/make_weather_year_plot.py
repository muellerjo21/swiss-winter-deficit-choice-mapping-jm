"""Figure of the rank per weather year (fig11, src/make_graphics.fig_rank_by_weather_year)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import MELLOT_COST_CHANGE_PCT
from make_graphics import fig_rank_by_weather_year, figure_settings


if __name__ == "__main__":
    p = snakemake.params
    cost = pd.Series(MELLOT_COST_CHANGE_PCT).reindex(p.scenario_ids)  # figure order as in all figures (2016 costs)
    fig_rank_by_weather_year(pd.read_csv(snakemake.input.summary), p.weather_years, figure_settings("regional", p, cost),
                             out_dir=Path(snakemake.output[0]).parent.parent, formats=p.formats)
