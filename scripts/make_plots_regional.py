"""Creates the figures of the regional main analysis (suffix _regional) from the regional results."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_LANGUAGE, LANGUAGE_REGION_WEIGHTS
from make_graphics import make_all_regional
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
    make_all_regional(
        attributes, weights, pd.read_csv(snakemake.input.rankings), pd.read_csv(snakemake.input.regions),
        pd.read_csv(snakemake.input.rank1_share), pd.read_csv(snakemake.input.curve),
        pd.read_csv(snakemake.input.switches), national,
        json.loads(Path(snakemake.input.elcom).read_text())["total_rp_kwh"], p.figure_scenarios,
        model_path=snakemake.input.choice_model, out_dir=Path(snakemake.output[0]).parent.parent,
        mobile_share=p.mobile_share, credible_interval=p.credible_interval, interval_type=p.interval_type)
