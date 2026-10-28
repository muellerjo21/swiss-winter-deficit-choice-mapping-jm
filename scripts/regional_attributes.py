"""Attributes per Calliope region and scenario (src/regional.py), regional ElCom reference values and population."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import load_canton_area, load_scenario_cost_and_demand
from regional import (municipality_regions, regional_attributes, regional_balance_import_share, regional_elcom_reference,
                      regional_population)


def attributes(paths_to_nc: list, scenario_ids: list, path_to_canton_area: str, path_to_national: str,
               path_to_prices: str, path_to_cantons: str, path_to_statpop: str, path_to_eur_chf: str, overrides: dict,
               path_to_attributes: str, path_to_elcom: str, path_to_population: str, path_to_imports: str,
               import_definition: str) -> None:
    regions = municipality_regions(pd.read_csv(path_to_cantons), overrides)
    elcom = regional_elcom_reference(pd.read_csv(path_to_prices), regions)
    population = regional_population(pd.read_csv(path_to_statpop), regions)
    area = load_canton_area(path_to_canton_area)
    national = pd.read_csv(path_to_national).set_index("scenario_id")
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    imports = pd.read_csv(path_to_imports).set_index("scenario_id")
    frames = []
    for s, nc in zip(scenario_ids, paths_to_nc):
        a = regional_attributes(nc, s, area, national.loc[s], *load_scenario_cost_and_demand(nc), elcom, eur_to_chf)
        if import_definition != "electricity":  # default keeps the national import_share unchanged
            a["import_share"] = imports.loc[s, f"import_share_{import_definition}"]
        a["import_share_balance"] = a["region"].map(regional_balance_import_share(nc))
        frames.append(a)
    pd.concat(frames, ignore_index=True).to_csv(path_to_attributes, index=False)
    elcom.rename_axis("region").to_csv(path_to_elcom)
    population.rename_axis("region").to_csv(path_to_population)


if __name__ == "__main__":
    attributes(
        paths_to_nc=list(snakemake.input.nc), scenario_ids=snakemake.params.scenario_ids,
        path_to_canton_area=snakemake.input.canton_area, path_to_national=snakemake.input.national,
        path_to_prices=snakemake.input.prices, path_to_cantons=snakemake.input.cantons,
        path_to_statpop=snakemake.input.statpop, path_to_eur_chf=snakemake.input.eur_chf,
        overrides=snakemake.params.overrides, path_to_attributes=snakemake.output.attributes,
        path_to_elcom=snakemake.output.elcom, path_to_population=snakemake.output.population,
        path_to_imports=snakemake.input.imports, import_definition=snakemake.params.import_definition,
    )
