"""Holt den nationalen ElCom-Referenzpreis (Median, Rp./kWh) eines Jahres via LINDAS."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import get_elcom_reference_price


def fetch(year: int, category: str, path_to_output: str) -> None:
    ref = {k: float(v) for k, v in get_elcom_reference_price(year, category).items()}
    Path(path_to_output).write_text(json.dumps({"year": year, "category": category, **ref}, indent=4))


if __name__ == "__main__":
    fetch(year=snakemake.params.year, category=snakemake.params.category, path_to_output=snakemake.output[0])
