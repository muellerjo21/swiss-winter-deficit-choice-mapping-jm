"""Figures of the regional main analysis (suffix _regional) and their attribute contributions."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_LANGUAGE, LANGUAGE_REGION_WEIGHTS
from make_graphics import figure_settings, make_all_regional
from regional import load_regional_model, population_weights, regional_utilities


if __name__ == "__main__":
    p = snakemake.params
    attributes = pd.read_csv(snakemake.input.attributes)
    population = pd.read_csv(snakemake.input.population).set_index("region")["population"]
    weights = population_weights(population, p.exclude)
    coefficients = {r: CANTON_LANGUAGE.get(r) for r in population.index}
    model = load_regional_model(snakemake.input.choice_model, p.mobile_share, LANGUAGE_REGION_WEIGHTS)
    _, samples, _, _ = regional_utilities(attributes, weights, coefficients, **model)  # fig5 needs the samples
    national = {s: samples["national"][s].to_numpy() for s in samples["national"].columns}
    cost = attributes.drop_duplicates("scenario_id").set_index("scenario_id")["mellot_cost_change_pct"].reindex(p.scenario_ids)
    make_all_regional(
        attributes, weights, pd.read_csv(snakemake.input.rankings), pd.read_csv(snakemake.input.regions),
        pd.read_csv(snakemake.input.rank1_share), pd.read_csv(snakemake.input.curve),
        pd.read_csv(snakemake.input.switches), national,
        json.loads(Path(snakemake.input.elcom).read_text())["total_rp_kwh"], figure_settings("regional", p, cost),
        model_path=snakemake.input.choice_model, out_dir=Path(snakemake.output.figures[0]).parent.parent,
        mobile_share=p.mobile_share).to_csv(snakemake.output.contributions, index=False)
