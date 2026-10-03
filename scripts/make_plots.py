"""Erzeugt alle Thesis-Abbildungen aus den Pipeline-Ergebnissen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from make_graphics import load_results, make_all


if __name__ == "__main__":
    attrs, rankings = load_results(snakemake.input.attributes, snakemake.input.rankings)
    make_all(attrs, rankings, model_path=snakemake.input.choice_model,
             out_dir=Path(snakemake.output[0]).parent)
