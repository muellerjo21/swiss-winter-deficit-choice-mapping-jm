"""Berechnet die Choice-Modell-Attribute (national) für ein Szenario."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import compute_all_attributes, load_canton_area


def scenario_attributes(scenario_id: str, path_to_nc: str, path_to_canton_area: str, path_to_eur_chf: str,
                        path_to_elcom: str, path_to_output: str) -> None:
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    elcom = json.loads(Path(path_to_elcom).read_text())
    elcom_ref = {k: elcom[k] for k in ("total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh")}
    row = compute_all_attributes(path_to_nc, load_canton_area(path_to_canton_area), elcom_ref, eur_to_chf)
    row["scenario_id"] = scenario_id
    pd.DataFrame([row]).to_csv(path_to_output, index=False)


if __name__ == "__main__":
    scenario_attributes(
        scenario_id=snakemake.wildcards.scenario,
        path_to_nc=snakemake.input.nc,
        path_to_canton_area=snakemake.input.canton_area,
        path_to_eur_chf=snakemake.input.eur_chf,
        path_to_elcom=snakemake.input.elcom,
        path_to_output=snakemake.output[0],
    )
