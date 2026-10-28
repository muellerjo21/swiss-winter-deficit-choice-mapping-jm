"""Figures of the national aggregate (appendix, suffix _national) and their attribute contributions."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from make_graphics import figure_settings, load_results, make_all


if __name__ == "__main__":
    p = snakemake.params
    attrs, rankings = load_results(snakemake.input.attributes, snakemake.input.rankings)
    cost = attrs.set_index("scenario_id")["mellot_cost_change_pct"].reindex(p.scenario_ids)
    make_all(attrs, rankings, figure_settings("national", p, cost), model_path=snakemake.input.choice_model,
             out_dir=Path(snakemake.output.figures[0]).parent.parent,
             mobile_share=p.mobile_share).to_csv(snakemake.output.contributions, index=False)
