"""Holt den EZB-Referenzkurs EUR/CHF eines festen Datums (einmal pro Lauf, gecacht in build/)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import fetch_eur_to_chf


def fetch(date: str, path_to_output: str) -> None:
    rate = fetch_eur_to_chf(date=date)
    Path(path_to_output).write_text(json.dumps({"date": date, "eur_to_chf": rate}, indent=4))


if __name__ == "__main__":
    fetch(date=snakemake.params.date, path_to_output=snakemake.output[0])
