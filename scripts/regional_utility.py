"""Regional main analysis (src/regional.py): rankings aggregated over the Calliope regions, ranking per region,
population share with each scenario on rank 1, sensitivities (excluded regions, import, land) and checks."""
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_MERGES, LANGUAGE_REGION_WEIGHTS
from intervals import hdi
from load_data import load_canton_area
from regional import (LANGUAGE_GROUPS, _shares, attribute_columns, load_regional_model, population_weights,
                      rank1_population_share, region_coefficients, region_table, regional_rankings, regional_utilities)
from utility import rank_with_uncertainty


def analyse(attributes, weights, coefficients, population, model, credible_interval, interval_type):
    u, s, points, region_samples = regional_utilities(attributes, weights, coefficients, **model)
    return (regional_rankings(attributes, u, s, credible_interval, interval_type),
            region_table(points, region_samples, weights, population, coefficients))


# Column of utility.rank_with_uncertainty (national code path) that equals a region's utility with these coefficients;
# 'national' = LANGUAGE_REGION_WEIGHTS mix of DE-CH and FR-CH = the 'mixed' coefficients (utility linear in beta)
NATIONAL_COLUMN_OF_COEFFICIENTS = {"DE-CH": "DE_CH", "FR-CH": "FR_CH", "mixed": "national"}


def checks(attributes, population, weights, coefficients, national, model, credible_interval, interval_type,
           path_to_canton_area, cantons, statpop, overrides, coefficient_overrides):
    """Consistency checks of the regional analysis: (name, value, tolerance)."""
    rows = [("weights sum to 1", abs(weights.sum() - 1), 1e-12),
            ("negative weights", float((weights < 0).sum()), 0),
            ("NaN in regional attributes", float(attributes[attribute_columns()].isna().sum().sum()), 0),
            ("NaN in shares of a region without capacity",
             float(sum(pd.isna(v) for v in _shares(pd.DataFrame({"canton": [], "tech": [], "capacity": []})).values())), 0),
            ("population total = STATPOP total", abs(population.sum() - statpop["population"].sum()), 0)]
    area = load_canton_area(path_to_canton_area)
    canton_of = dict(zip(cantons["bfs_nr"], cantons["canton"])) | {int(k): v for k, v in overrides.items()}
    canton_pop = statpop.groupby(statpop["bfs_nr"].map(canton_of))["population"].sum()
    for merged, parts in CANTON_MERGES.items():
        rows.append((f"area {merged} = sum of {'+'.join(parts)}", abs(area[merged] - sum(area[p] for p in parts)), 1e-9))
        rows.append((f"population {merged} = sum of {'+'.join(parts)}", abs(population[merged] - sum(canton_pop[p] for p in parts)), 0))
    # artificial constellation: all regions with the national attributes and DE-CH coefficients -> national DE-CH result
    art = attributes.copy()
    for c in attribute_columns():
        art[c] = art["scenario_id"].map(national[c])
    all_weights = population_weights(population, [])
    r_art, _ = analyse(art, all_weights, {r: "DE-CH" for r in population.index}, population, model, credible_interval, interval_type)
    r_art = r_art.set_index("scenario_id")
    nat = rank_with_uncertainty(national.reset_index(), {l: model["betas_mean"][l] for l in LANGUAGE_GROUPS},
                                {l: model["betas_samples"][l] for l in LANGUAGE_GROUPS}, model["scale"], LANGUAGE_REGION_WEIGHTS,
                                model["mobile_mean"], model["mobile_samples"], model["mobile_share"], credible_interval, interval_type).set_index("scenario_id")
    rows += [("artificial: utility = national DE-CH", float((r_art["utility_national"] - nat.loc[r_art.index, "utility_DE_CH"]).abs().max()), 1e-12),
             ("artificial: P(rank 1) = national DE-CH", float((r_art["p_rank1_national"] - nat.loc[r_art.index, "p_rank1_DE_CH"]).abs().max()), 1e-12),
             ("artificial: ranks = national DE-CH", float((r_art["rank_national"] != nat.loc[r_art.index, "rank_DE_CH"]).sum()), 0)]
    # own HDI (src/intervals.py, used everywhere) = arviz.hdi on the regional utility samples of all scenarios
    _, samples, points, _ = regional_utilities(attributes, weights, coefficients, **model)
    dev = max(abs(a - b) for df in samples.values() for c in df.columns
              for a, b in zip(hdi(df[c], credible_interval), np.asarray(az.hdi(df[c].to_numpy(), prob=credible_interval))))
    rows.append(("HDI = arviz.hdi", float(dev), 0))
    # regions with overridden coefficients (TI): regional utility = national code path on the region's attributes
    nat_model = ({l: model["betas_mean"][l] for l in LANGUAGE_GROUPS}, {l: model["betas_samples"][l] for l in LANGUAGE_GROUPS},
                 model["scale"], LANGUAGE_REGION_WEIGHTS, model["mobile_mean"], model["mobile_samples"], model["mobile_share"],
                 credible_interval, interval_type)
    for region, coef in coefficient_overrides.items():
        own = rank_with_uncertainty(attributes[attributes["region"] == region], *nat_model).set_index("scenario_id")
        column = f"utility_{NATIONAL_COLUMN_OF_COEFFICIENTS[coef]}"
        rows.append((f"{region}: utility = {coef} utility with {region} attributes",
                     float((points[region] - own.loc[points[region].index, column]).abs().max()), 1e-12))
    out = pd.DataFrame(rows, columns=["check", "value", "tolerance"])
    out["passed"] = out["value"] <= out["tolerance"]
    return out


def regional(path_to_attributes, path_to_population, path_to_national, path_to_choice_model, path_to_canton_area,
             path_to_cantons, path_to_statpop, exclude, coefficient_overrides, excluded_coefficients, overrides, mobile_share,
             credible_interval, interval_type, path_to_imports, out):
    attributes = pd.read_csv(path_to_attributes)
    population = pd.read_csv(path_to_population).set_index("region")["population"]
    national = pd.read_csv(path_to_national).set_index("scenario_id")
    model = load_regional_model(path_to_choice_model, mobile_share, LANGUAGE_REGION_WEIGHTS)
    weights = population_weights(population, exclude)
    coefficients = region_coefficients(population.index, coefficient_overrides)

    rankings, table = analyse(attributes, weights, coefficients, population, model, credible_interval, interval_type)
    rankings.to_csv(out["rankings"], index=False)
    table.to_csv(out["regions"], index=False)
    rank1_population_share(table).rename("population_share_rank1").rename_axis("scenario_id").to_csv(out["rank1_share"])

    variants = {"main": rankings}
    # TI (excluded or with overridden coefficients) with each of the excluded_coefficients, all regions included
    optional = sorted(set(exclude) | set(coefficient_overrides))
    label = "excluded regions" if exclude else "+".join(optional)
    for c in excluded_coefficients:
        variants[f"{label} with {c} coefficients"], _ = analyse(
            attributes, population_weights(population, []), {**coefficients, **{r: c for r in optional}}, population, model, credible_interval, interval_type)
    variants["import: regional balance"], _ = analyse(attributes.assign(import_share=attributes["import_share_balance"]),
                                                      weights, coefficients, population, model, credible_interval, interval_type)
    variants["land: national share"], _ = analyse(attributes.assign(relative_land=attributes["relative_land_national"]),
                                                  weights, coefficients, population, model, credible_interval, interval_type)
    # fuel imports counted with their energy content: 1 GWh fuel = 1 GWh electricity (src/load_data.import_quantities)
    imports = pd.read_csv(path_to_imports).set_index("scenario_id")
    for definition, label in [("electricity_fuels", "import: electricity + fuels (year)"),
                              ("electricity_fuels_diesel", "import: electricity + fuels + synthetic diesel (year)")]:
        variants[label], _ = analyse(attributes.assign(import_share=attributes["scenario_id"].map(imports[f"import_share_{definition}"])),
                                     weights, coefficients, population, model, credible_interval, interval_type)
    pd.concat(variants, names=["variant", "row"]).reset_index(level="variant").to_csv(out["sensitivities"], index=False)

    checks(attributes, population, weights, coefficients, national, model, credible_interval, interval_type,
           path_to_canton_area, pd.read_csv(path_to_cantons), pd.read_csv(path_to_statpop), overrides,
           coefficient_overrides).to_csv(out["checks"], index=False)


if __name__ == "__main__":
    p = snakemake.params
    regional(snakemake.input.attributes, snakemake.input.population, snakemake.input.national, snakemake.input.choice_model,
             snakemake.input.canton_area, snakemake.input.cantons, snakemake.input.statpop, p.exclude,
             p.coefficient_overrides, p.excluded_coefficients, p.overrides, p.mobile_share, p.credible_interval, p.interval_type,
             snakemake.input.imports, dict(snakemake.output.items()))
