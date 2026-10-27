"""Fetches the permanent resident population per municipality (BFS STATPOP, 31 Dec of a completed year)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import fetch_statpop


if __name__ == "__main__":
    fetch_statpop(snakemake.params.year, snakemake.params.table).to_csv(snakemake.output[0], index=False)
