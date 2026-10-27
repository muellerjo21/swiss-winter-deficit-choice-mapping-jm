"""Fetches the ElCom tariff rows (Rp./kWh) of all municipalities for one year and category via LINDAS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import fetch_elcom_price


if __name__ == "__main__":
    fetch_elcom_price(snakemake.params.year, snakemake.params.category).to_csv(snakemake.output[0], index=False)
