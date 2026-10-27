"""Fetches the municipality -> canton assignment of the LINDAS register (incl. historical municipalities)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import fetch_municipality_cantons


if __name__ == "__main__":
    fetch_municipality_cantons().to_csv(snakemake.output[0], index=False)
