"""Attributes per Calliope region and scenario (src/regional.py), regional ElCom reference values and population."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from load_data import load_canton_area, scope_reference_table
from regional import municipality_regions, regional_attribute_table, regional_elcom_reference, regional_population


def attributes(paths_to_nc: list, scenario_ids: list, path_to_canton_area: str, path_to_national: str,
               path_to_prices: str, path_to_cantons: str, path_to_statpop: str, path_to_eur_chf: str, overrides: dict,
               path_to_attributes: str, path_to_elcom: str, path_to_population: str, path_to_imports: str,
               import_definition: str, cost_scale: float, cost_scope: str, cost_groups: dict, power_fuel: dict,
               energy_reference: float) -> None:
    regions = municipality_regions(pd.read_csv(path_to_cantons), overrides)
    elcom = regional_elcom_reference(pd.read_csv(path_to_prices), regions)
    population = regional_population(pd.read_csv(path_to_statpop), regions)
    area = load_canton_area(path_to_canton_area)
    national = pd.read_csv(path_to_national).set_index("scenario_id")
    eur_to_chf = json.loads(Path(path_to_eur_chf).read_text())["eur_to_chf"]
    imports = pd.read_csv(path_to_imports).set_index("scenario_id")
    price_reference = scope_reference_table(elcom, cost_scope, energy_reference)  # elcom_by_region.csv stays ElCom
    # default (electricity) keeps the national import_share unchanged
    import_share = None if import_definition == "electricity" else imports[f"import_share_{import_definition}"].to_dict()
    cost_options = dict(cost_scale=cost_scale, cost_scope=cost_scope, cost_groups=cost_groups, power_fuel=power_fuel)
    regional_attribute_table(dict(zip(scenario_ids, paths_to_nc)), area, national, price_reference, eur_to_chf,
                             cost_options, import_share).to_csv(path_to_attributes, index=False)
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
        cost_scale=snakemake.params.cost_scale,
        cost_scope=snakemake.params.cost_scope,
        cost_groups=snakemake.params.cost_groups,
        power_fuel=snakemake.params.power_fuel,
        energy_reference=snakemake.params.energy_reference,
    )
