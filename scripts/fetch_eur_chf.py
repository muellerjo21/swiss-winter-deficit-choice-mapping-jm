"""Fetches the annual mean ECB EUR/CHF rate of the base year (once per run, cached in build/)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import fetch_eur_to_chf


def fetch(year: int, path_to_output: str) -> None:
    rate, n_days = fetch_eur_to_chf(year)
    Path(path_to_output).write_text(json.dumps({"year": year, "eur_to_chf": rate, "n_days": n_days}, indent=4))


if __name__ == "__main__":
    fetch(year=snakemake.params.year, path_to_output=snakemake.output[0])
