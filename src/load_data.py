"""
Load and extract fitted coefficients from Tröndle, Mey & Lilliestam's (2025)
discrete choice model.

The pipeline selects the model file with data.choice_model (entries of data.choice_models): 11 attributes; the
Swiss coefficient groups DE-CH / FR-CH (per region via regions.language) are mapped to a group or country of the file
(model_partworths): the January 2026 model has partworths per language group (DA/DE/DE-CH/EN/FR/FR-CH/PL/PT/SO/SV), the
measured model (Nov 2026) a European mean plus a country effect per country (one level Switzerland).

Also: the attributes of a scenario from its Calliope result file, the price formula and the downloads of the fetch
rules (ElCom, municipality register, STATPOP, EUR/CHF).
"""

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
import certifi
import arviz as az
import numpy as np
import pandas as pd
import requests
import xarray as xr
from SPARQLWrapper import SPARQLWrapper, JSON

from config import (
    CANTON_LANGUAGE, FOREIGN_CODES, CANTON_NAME_TO_CODE, CANTON_MERGES, CAPACITY_DENSITY_GW_PER_KM2, OWNERSHIP_MAPPING,
    TECH_SOURCE_MAPPING, PV_REFERENCE_TECHS, CHOICE_MODEL_COUNTRIES, SECTOR_COUPLING_ELEC_TECHS, OWNERSHIP_EXCLUDED_TECHS,
    SOURCE_EXCLUDED_TECHS, MELLOT_COST_CHANGE_PCT, END_USE_TECHS, TRANSMISSION_CHANGE, COST_CLASS, HEAT_DEMAND_TECHS,
    TRANSPORT_MARKER, SOURCES, ELCOM_PRODUCT, ELECTRICITY_CARRIER, DEMAND_ELECTRICITY_TECH, DEMAND_TECH_PREFIX,
    TRANSMISSION_TECH,
)
from checks import check_technology_mapping, cost_class, require_selection

# Variables of the Calliope result files used by the workflow
RESULT_VARIABLES = ["carrier_prod", "carrier_con", "energy_cap", "cost"]


@lru_cache(maxsize=1)
def _read_result(nc_path: str) -> xr.Dataset:
    with xr.open_dataset(nc_path) as ds:
        return ds[RESULT_VARIABLES].load()


def result_dataset(nc_path) -> xr.Dataset:
    """The used variables (RESULT_VARIABLES) of a Calliope result file, read from disk once and kept in memory for the
    following calls with the same file (the scripts process one file after the other; the last file stays cached).
    The values are the same as read directly from the file; callers must not modify the dataset."""
    return _read_result(str(nc_path))


def model_partworths(posterior, data_path, group: str):
    """Partworths (chain, draw, attribute) of a coefficient group: the group's own beta_partworths if the file has them
    per group (January 2026 model), otherwise the European mean beta_partworths plus the country effect effect_country
    (measured model). The group (e.g. DE-CH) is mapped to the file's group/country by data.choice_models.<entry>.
    coefficients (CHOICE_MODEL_COUNTRIES); a group without mapping is used as it is."""
    country = CHOICE_MODEL_COUNTRIES.get(str(Path(data_path).resolve()), {}).get(group, group)
    beta = posterior["beta_partworths"]
    if "country" in beta.dims:
        return beta.sel(country=country)
    return beta + posterior["effect_country"].sel(country=country)


def load_beta_partworths_mean(data_path, country: str) -> pd.DataFrame:
    """
    Load the fitted choice model and extract posterior-MEAN beta values
    for one country/region (a single point estimate per attribute).

    Parameters
    ----------
    data_path : str or Path
        Path to the .nc file of the choice model (data.choice_models).
    country : str
        Coefficient group, mapped to the file's group/country by model_partworths
        (DE-CH / FR-CH for Switzerland; the January 2026 model also takes DA/DE/EN/FR/PL/PT/SO/SV).
        No default on purpose -- the valid values differ between the model files,
        so picking a wrong implicit default silently gives the wrong region.

    Use this for a first, quick pass (fixed betas). See
    `load_beta_partworths_samples` for the full posterior, needed for
    uncertainty quantification (credible intervals on utility/ranking).

    Returns
    -------
    pd.DataFrame with columns: attribute, beta_mean
    """
    idata = az.from_netcdf(data_path)
    beta = model_partworths(idata.posterior, data_path, country)
    beta_mean = beta.mean(dim=["chain", "draw"])
    df = beta_mean.to_dataframe(name="beta_mean").reset_index()
    return df[["attribute", "beta_mean"]]


def load_beta_partworths_samples(data_path, country: str) -> dict:
    """
    Load the fitted choice model and extract ALL posterior samples of beta
    for one country/region, one array per attribute.

    Unlike `load_beta_partworths_mean`, this keeps every individual sample
    (chain x draw), so utility can be computed once per sample, giving a
    distribution of utility values per scenario instead of a single point estimate.

    Parameters
    ----------
    data_path : str or Path
        Path to the .nc file of the choice model (data.choice_models).
    country : str
        See `load_beta_partworths_mean` for valid values per file.

    Returns
    -------
    dict[str, np.ndarray]
        Keys are attribute labels: the 11 fitted
        attributes: source_wind, source_coal, source_gas, source_nuclear,
        source_biomass, cost, import, transmission, land, ownership_commercial,
        ownership_community. PV/solar is the implicit zero-beta reference for the
        source_* group, and ownership_public is the implicit reference for ownership.
        Values are 1D numpy arrays of length (n_chains * n_draws), the
        full set of posterior samples for that attribute's beta.
        All arrays have the same length and the same sample order, so
        beta_samples["cost"][i] and beta_samples["land"][i] both come
        from the same posterior draw i -- keep them aligned when computing
        utility per sample.
    """
    idata = az.from_netcdf(data_path)
    beta = model_partworths(idata.posterior, data_path, country)

    # Combine the chain and draw dimensions into one "sample" dimension,
    # so each attribute's samples are a simple 1D array.
    beta_stacked = beta.stack(sample=("chain", "draw"))

    samples = {}
    for attr in beta_stacked.coords["attribute"].values:
        samples[attr] = beta_stacked.sel(attribute=attr).values

    return samples


def load_mobile_partworths_mean(data_path) -> pd.DataFrame:
    """
    Posterior-MEAN of mobile_partworths, the additive shift of the partworths for respondents
    with m=1 (constant_data/m) in the Jan 2026 model (data.choice_models.jan_2026):
        u = sum_k z_k / sigma_k * (beta_partworths[country, k] + m * mobile_partworths[k])
    verified against u_left/u_right in the posterior. Not region-specific (no country dim).
    The reading "m=1 = answered on a mobile device" rests on the variable name only; the
    file contains no further documentation of m.

    Returns
    -------
    pd.DataFrame with columns: attribute, mobile_mean; None if the model has no mobile_partworths
    """
    idata = az.from_netcdf(data_path)
    if "mobile_partworths" not in idata.posterior:
        return None  # model without mobile shift (measured model); utility checks that mobile_share is 0
    mobile_mean = idata.posterior["mobile_partworths"].mean(dim=["chain", "draw"])
    df = mobile_mean.to_dataframe(name="mobile_mean").reset_index()
    return df[["attribute", "mobile_mean"]]


def load_mobile_partworths_samples(data_path) -> dict:
    """
    All posterior samples of mobile_partworths, one array per attribute, stacked exactly like
    `load_beta_partworths_samples` (chain x draw -> sample), so mobile_samples[attr][i] and
    beta_samples[attr][i] come from the same posterior draw i.

    Returns
    -------
    dict[str, np.ndarray] with the same keys and array length as load_beta_partworths_samples
    """
    idata = az.from_netcdf(data_path)
    if "mobile_partworths" not in idata.posterior:
        return None  # see load_mobile_partworths_mean
    mobile_stacked = idata.posterior["mobile_partworths"].stack(sample=("chain", "draw"))
    return {attr: mobile_stacked.sel(attribute=attr).values
            for attr in mobile_stacked.coords["attribute"].values}


def _load_loc_tech_variable(nc_path: str, variable: str, value_name: str) -> pd.DataFrame:
    """Load a Calliope loc_tech-indexed variable, split into canton/tech, add language region."""
    ds = result_dataset(nc_path)
    values = ds[variable].to_pandas()
    values.index = values.index.str.split("::", expand=True)
    values.index.names = ["canton", "tech"]
    values = values.reset_index(name=value_name)
    values["language_region"] = values["canton"].map(CANTON_LANGUAGE)
    return values


def load_scenario_capacity(nc_path: str) -> pd.DataFrame:
    df = _load_loc_tech_variable(nc_path, "energy_cap", "capacity")
    return df[~df["canton"].isin(FOREIGN_CODES)].copy()


def get_ch_import_carrier_techs(ds) -> list[str]:
    """loc_tech_carriers_prod entries with a Swiss canton as origin and a foreign country as
    destination -> carrier_prod on these = import into Switzerland."""
    prod_coords = ds.coords["loc_tech_carriers_prod"].values
    result = []
    for c in prod_coords:
        origin, _, rest = c.partition("::")
        if TRANSMISSION_TECH not in rest:
            continue
        dest = rest.partition(":")[2].partition("::")[0]
        if origin not in FOREIGN_CODES and dest in FOREIGN_CODES:
            result.append(c)
    return result


def aggregate_national(df: pd.DataFrame, value_col: str) -> float:
    """Sums an attribute column over all cantons into one national value."""
    return df[value_col].sum()


def load_canton_area(csv_path: str) -> dict:
    """Loads canton areas (km²) from the Statista CSV and maps them to canton codes,
    incl. the merged codes (AI_AR, BL_BS, NW_OW) from Calliope data."""
    df = pd.read_csv(csv_path, sep=";")
    df.columns = ["canton_name", "area_km2"]
    df["canton_name"] = df["canton_name"].str.strip()
    df["canton_code"] = df["canton_name"].map(CANTON_NAME_TO_CODE)

    area = dict(zip(df["canton_code"], df["area_km2"]))
    for merged_code, parts in CANTON_MERGES.items():
        area[merged_code] = sum(area[p] for p in parts)

    return area


def compute_land_from_capacity(capacity_df: pd.DataFrame, area_dict: dict, density_dict: dict = CAPACITY_DENSITY_GW_PER_KM2) -> pd.DataFrame:
    """Computes land use from installed capacity via technology-specific capacity density
    (GW/km²), following Tröndle et al.'s methodology (0.008 GW/km² = 8 MW/km² wind,
    0.08 GW/km² = 80 MW/km² PV). Capacity (Calliope energy_cap) is in GW and density in GW/km²,
    so GW / (GW/km²) = km²."""
    df = capacity_df[capacity_df["tech"].isin(density_dict.keys())].copy()
    df["density_gw_per_km2"] = df["tech"].map(density_dict)
    df["land_use_km2"] = df["capacity"] / df["density_gw_per_km2"]
    df["canton_area_km2"] = df["canton"].map(area_dict)
    df["relative_land"] = df["land_use_km2"] / df["canton_area_km2"]
    return df


def load_scenario_net_import(nc_path: str) -> pd.DataFrame:
    """Net electricity import (import - export) per Swiss cross-border line, in GWh."""
    ds = result_dataset(nc_path)
    import_techs = require_selection(get_ch_import_carrier_techs(ds), "cross-border lines", nc_path)

    imp = ds["carrier_prod"].sel(loc_tech_carriers_prod=import_techs).sum(dim="timesteps")
    exp = ds["carrier_con"].sel(loc_tech_carriers_con=import_techs).sum(dim="timesteps")

    net_values = imp.values - abs(exp.values)
    net = pd.DataFrame({
        "loc_tech_carrier": import_techs,
        "net_import_gwh": net_values,
    })
    net[["canton", "tech_carrier"]] = net["loc_tech_carrier"].str.split("::", n=1, expand=True)
    net["language_region"] = net["canton"].map(CANTON_LANGUAGE)
    return net


def get_ch_demand_elec_techs(ds) -> list[str]:
    con_coords = ds.coords["loc_tech_carriers_con"].values
    return [c for c in con_coords if f"::{DEMAND_ELECTRICITY_TECH}::" in c and c.split("::")[0] not in FOREIGN_CODES]


def get_ch_total_electricity_demand_techs(ds) -> list[str]:
    """demand_elec plus electricity consumption from sector coupling (SECTOR_COUPLING_ELEC_TECHS) at
    Swiss locations. Storage (pumped_hydro, hydrogen_electricity_storage, battery) deliberately
    excluded -- stored electricity is released again later and would be counted twice."""
    con_coords = ds.coords["loc_tech_carriers_con"].values
    sector_coupling = [
        c for c in con_coords
        if c.split("::")[0] not in FOREIGN_CODES
        and c.split("::")[1] in SECTOR_COUPLING_ELEC_TECHS
        and c.endswith(f"::{ELECTRICITY_CARRIER}")
    ]
    return require_selection(get_ch_demand_elec_techs(ds), "electricity demand at the Swiss locations") + sector_coupling


def load_scenario_demand(nc_path: str) -> pd.DataFrame:
    """Total electricity consumption per Swiss canton and tech (demand_elec + sector coupling), in GWh."""
    ds = result_dataset(nc_path)
    demand_techs = get_ch_total_electricity_demand_techs(ds)
    demand = (
        ds["carrier_con"]
        .sel(loc_tech_carriers_con=demand_techs)
        .sum(dim="timesteps")
        .pipe(abs)
        .to_pandas()
        .rename("demand_gwh")
        .reset_index()
    )
    demand[["canton", "tech_carrier"]] = demand["loc_tech_carriers_con"].str.split("::", n=1, expand=True)
    demand["language_region"] = demand["canton"].map(CANTON_LANGUAGE)
    return demand


def compute_import_share(nc_path: str) -> float:
    """National import share = net import / total consumption, clipped to [0, 1]
    (the survey attribute has no negative values / net export)."""
    net_import = aggregate_national(load_scenario_net_import(nc_path), "net_import_gwh")
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    share = net_import / demand
    return max(0.0, min(1.0, share))


IMPORT_DEFINITIONS = ("electricity", "electricity_fuels", "electricity_fuels_diesel")


def load_fuel_imports(nc_path: str, techs: dict) -> dict:
    """Annual fuel imports into Switzerland per import technology (GWh): carrier_prod of tech::carrier (techs
    {tech: carrier}) summed over all time steps and Swiss locations. Technologies absent from the scenario count 0."""
    ds = result_dataset(nc_path)
    prod = ds.coords["loc_tech_carriers_prod"].values
    out = {}
    for tech, carrier in techs.items():
        sel = [c for c in prod if c.split("::")[0] not in FOREIGN_CODES and c.split("::")[1] == tech
               and c.split("::")[2] == carrier]
        out[tech] = float(ds["carrier_prod"].sel(loc_tech_carriers_prod=sel).sum()) if sel else 0.0
    return out


def import_quantities(nc_path: str, fuel_techs: dict, diesel_techs: dict, denominator: str) -> dict:
    """Net electricity import, fuel imports and electricity consumption (annual sums, GWh) and the import shares of
    the three definitions (IMPORT_DEFINITIONS), each clipped to [0, 1]. The electricity share is computed exactly
    as compute_import_share. Fuel variants add the fuel imports to the net electricity import, counted with their
    energy content: 1 GWh fuel = 1 GWh electricity (no conversion efficiency; an assumption).
    denominator (imports.denominator): electricity = electricity consumption; final_energy = final energy
    (load_scenario_final_energy), reported in the extra column final_energy_gwh."""
    net_import = aggregate_national(load_scenario_net_import(nc_path), "net_import_gwh")
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    fuels = load_fuel_imports(nc_path, fuel_techs)
    diesel = load_fuel_imports(nc_path, diesel_techs)
    totals = {"electricity": net_import, "electricity_fuels": net_import + sum(fuels.values()),
              "electricity_fuels_diesel": net_import + sum(fuels.values()) + sum(diesel.values())}
    row = {"net_electricity_import_gwh": net_import, **{f"{t}_gwh": v for t, v in {**fuels, **diesel}.items()},
           "consumption_gwh": demand}
    if denominator == "final_energy":
        demand = load_scenario_final_energy(nc_path)["final_energy"]
        row["final_energy_gwh"] = demand
    elif denominator != "electricity":
        raise ValueError(f"imports.denominator must be electricity or final_energy, got {denominator!r}")
    for name in IMPORT_DEFINITIONS:
        row[f"import_share_{name}_unclipped"] = totals[name] / demand
        row[f"import_share_{name}"] = max(0.0, min(1.0, totals[name] / demand))
    return row


def compute_ownership_shares(capacity_df: pd.DataFrame, mapping: dict = OWNERSHIP_MAPPING) -> dict:
    """Capacity-weighted expected value for ownership_commercial / ownership_community,
    based on a fixed technology-to-owner mapping (assumption, not empirical).
    The reference category 'public' has no beta of its own in the choice model (implicit reference)."""
    df = capacity_df[capacity_df["tech"].isin(mapping.keys())].copy()
    df["ownership_category"] = df["tech"].map(mapping)
    total_capacity = df["capacity"].sum()
    shares = df.groupby("ownership_category")["capacity"].sum() / total_capacity
    return {
        "ownership_commercial": shares.get("commercial", 0.0),
        "ownership_community": shares.get("community", 0.0),
        "ownership_public": shares.get("public", 0.0),  # for checking only, not used with a beta
    }


# Source attributes of the choice model, in the column order of the attribute tables
SOURCE_CATEGORIES = ("source_wind", "source_gas", "source_biomass", "source_coal", "source_nuclear")


def compute_technology_mix_shares(capacity_df: pd.DataFrame, mapping: dict = TECH_SOURCE_MAPPING) -> dict:
    """Capacity share per source_* category. The denominator (total_capacity) includes ALL
    generation-relevant technologies incl. the PV reference category (PV_REFERENCE_TECHS);
    otherwise leaving out PV capacity would artificially shrink the denominator and overstate all shares."""
    relevant_techs = list(mapping.keys()) + PV_REFERENCE_TECHS
    df = capacity_df[capacity_df["tech"].isin(relevant_techs)].copy()
    df["source_category"] = df["tech"].map(mapping)
    total_capacity = df["capacity"].sum()
    shares = df.groupby("source_category")["capacity"].sum() / total_capacity
    # every source category of the choice model; a category without mapped technology (coal, nuclear: no Swiss
    # technology in attributes.source) has share 0
    return {category: shares.get(category, 0.0) for category in SOURCE_CATEGORIES}


ELCOM_SPARQL_ENDPOINT = SOURCES["lindas_sparql"]


def _use_certifi_certificates() -> None:
    """CA certificates of certifi for the downloads (SPARQLWrapper and requests), set only when downloading."""
    os.environ["SSL_CERT_FILE"] = certifi.where()


def fetch_elcom_price(year: int, category: str, product: str = ELCOM_PRODUCT) -> pd.DataFrame:
    """Fetches ElCom electricity prices (Rp./kWh) per municipality directly via the LINDAS SPARQL
    endpoint instead of hard-coding values. category e.g. 'H4' = standard household category
    (price.category in config/default.yaml)."""
    query = f"""
    PREFIX schema: <http://schema.org/>
    PREFIX cube: <https://cube.link/>
    PREFIX elcom: <https://energy.ld.admin.ch/elcom/electricityprice/dimension/>
    SELECT ?municipality_id ?category ?energy ?grid ?charge ?aidfee ?fixcosts ?total
    FROM <https://lindas.admin.ch/elcom/electricityprice>
    FROM <https://lindas.admin.ch/territorial>
    WHERE {{
      <https://energy.ld.admin.ch/elcom/electricityprice/observation/> cube:observation ?observation.
      ?observation
        elcom:category/schema:name ?category;
        elcom:municipality ?municipality_id;
        elcom:period "{year}"^^<http://www.w3.org/2001/XMLSchema#gYear>;
        elcom:product <https://energy.ld.admin.ch/elcom/electricityprice/product/{product}>;
        elcom:fixcosts ?fixcosts;
        elcom:total ?total;
        elcom:gridusage ?grid;
        elcom:energy ?energy;
        elcom:charge ?charge;
        elcom:aidfee ?aidfee.
      FILTER(?category = "{category}")
    }}
    """
    _use_certifi_certificates()
    sparql = SPARQLWrapper(ELCOM_SPARQL_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    rows = [
        {k: (float(v["value"]) if v["type"] == "literal" and k != "category" else v["value"])
         for k, v in r.items()}
        for r in results["results"]["bindings"]
    ]
    return pd.DataFrame(rows)


def fetch_municipality_cantons() -> pd.DataFrame:
    """Municipality (BFS number, incl. historical municipalities) -> canton abbreviation, from the LINDAS
    register of the Federal Statistical Office (graph fso/register). Municipalities without a canton in the
    register (e.g. Moutier after its change from BE to JU) are missing and are added via
    spatial.regional.municipality_canton_overrides."""
    query = """
    SELECT ?municipality ?canton WHERE { GRAPH <https://lindas.admin.ch/fso/register> {
      ?m a <https://schema.ld.admin.ch/Municipality> ; <http://schema.org/identifier> ?municipality ;
         <http://schema.org/containedInPlace> ?c .
      ?c a <https://schema.ld.admin.ch/Canton> ; <http://schema.org/alternateName> ?canton } }
    """
    _use_certifi_certificates()
    sparql = SPARQLWrapper(ELCOM_SPARQL_ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    rows = sparql.query().convert()["results"]["bindings"]
    df = pd.DataFrame({"bfs_nr": [int(r["municipality"]["value"]) for r in rows],
                       "canton": [r["canton"]["value"] for r in rows]})
    return df.drop_duplicates().sort_values("bfs_nr").reset_index(drop=True)


STATPOP_API = SOURCES["statpop_pxweb"]


def fetch_statpop(year: int, table: str) -> pd.DataFrame:
    """Permanent resident population per municipality on 31 December of a completed year (BFS STATPOP via
    the PxWeb API, municipalities in the table's current boundaries). Returns bfs_nr, name, population."""
    if year >= date.today().year:
        raise ValueError(f"STATPOP needs a completed year, got {year} (current year {date.today().year}).")
    _use_certifi_certificates()
    url = STATPOP_API.format(table=table)
    meta = requests.get(url, timeout=60)
    meta.raise_for_status()
    geo = next(v for v in meta.json()["variables"] if v["code"].startswith("Kanton"))
    municipalities = [(c, t) for c, t in zip(geo["values"], geo["valueTexts"]) if t.startswith("......")]
    total = {"Staatsangehörigkeit (Kategorie)": "-99999", "Geschlecht": "-99999", "Alter": "-99999"}
    query = [{"code": "Jahr", "selection": {"filter": "item", "values": [str(year)]}},
             {"code": geo["code"], "selection": {"filter": "item", "values": [c for c, _ in municipalities]}},
             {"code": "Bevölkerungstyp", "selection": {"filter": "item", "values": ["1"]}}]  # permanent residents
    query += [{"code": k, "selection": {"filter": "item", "values": [v]}} for k, v in total.items()]
    response = requests.post(url, json={"query": query, "response": {"format": "json"}}, timeout=300)
    response.raise_for_status()
    names = dict(municipalities)
    rows = [{"bfs_nr": int(d["key"][1]), "name": names[d["key"][1]].lstrip("."), "population": float(d["values"][0])}
            for d in response.json()["data"]]
    return pd.DataFrame(rows).sort_values("bfs_nr").reset_index(drop=True)


def elcom_reference_from_prices(df: pd.DataFrame) -> dict:
    """Reference price (median of the total price), taxes/levies (median of charge + aid fee) and grid usage
    (median) over the given ElCom tariff rows (as returned by fetch_elcom_price), in Rp./kWh. Used for the
    national reference and, per Calliope region, for the regional analysis."""
    return {
        "total_rp_kwh": df["total"].median(),
        "taxes_levies_rp_kwh": (df["charge"] + df["aidfee"]).median(),
        "netznutzung_rp_kwh": df["grid"].median(),
    }


def get_elcom_reference_price(year: int, category: str) -> dict:
    """National median electricity price and the taxes/levies component, directly from ElCom via
    LINDAS (no hard-coding). Returned in Rp./kWh."""
    return elcom_reference_from_prices(fetch_elcom_price(year, category))


def load_scenario_system_cost(nc_path: str) -> float:
    """Total Swiss system cost (million EUR/year), summed over all Swiss loc_techs
    (foreign loc_techs excluded, as for the other attributes). The cost class is 'monetary'; the result
    files state neither currency nor price year, EUR is our assumption."""
    ds = result_dataset(nc_path)
    cost = ds["cost"]
    classes = list(cost.coords["costs"].values)
    cost = cost.sel(costs=cost_class(classes, COST_CLASS))
    loc_techs = cost.coords["loc_techs_cost"].values
    ch_loc_techs = [lt for lt in loc_techs if lt.split("::")[0] not in FOREIGN_CODES]
    total = cost.sel(loc_techs_cost=ch_loc_techs).sum().item()
    return total  # million EUR/year


def cost_group_of(tech: str, groups: dict) -> str:
    """Cost group (price.cost_groups) of a Calliope technology; ac_transmission:<region> -> ac_transmission. Fails if
    the technology is in no group or in several."""
    base = tech.split(":")[0]
    found = [g for g, techs in groups.items() if base in techs]
    if len(found) != 1:
        raise ValueError(f"technology {tech!r} is in {len(found)} cost groups ({found}), expected exactly one; "
                         "see price.cost_groups in config/default.yaml")
    return found[0]


def load_scenario_cost_by_technology(nc_path: str, groups: dict) -> pd.DataFrame:
    """Swiss system cost (million EUR/year) per technology (summed over the Swiss locations) with its cost group;
    the costs sum to load_scenario_system_cost."""
    ds = result_dataset(nc_path)
    cost = ds["cost"]
    classes = list(cost.coords["costs"].values)
    cost = cost.sel(costs=cost_class(classes, COST_CLASS)).to_pandas()
    cost = cost[[lt.split("::")[0] not in FOREIGN_CODES for lt in cost.index]]
    by_tech = cost.groupby([lt.split("::")[1] for lt in cost.index]).sum().rename("cost").rename_axis("tech").reset_index()
    by_tech["group"] = [cost_group_of(t, groups) for t in by_tech["tech"]]
    return by_tech


def _swiss_flows(ds) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Annual production, consumption (positive, GWh) per (tech, carrier) and cost (million EUR) per tech at the Swiss
    locations, without transmission links (tech:<region>)."""
    def by_tech_carrier(var):
        v = ds[var].sum("timesteps").to_pandas().abs()
        keep = [i for i in v.index if i.split("::")[0] not in FOREIGN_CODES and ":" not in i.split("::")[1]]
        v = v[keep]
        df = pd.DataFrame({"tech": [i.split("::")[1] for i in v.index], "carrier": [i.split("::")[2] for i in v.index],
                           "value": v.to_numpy()})
        return df.groupby(["tech", "carrier"])["value"].sum()
    cost = ds["cost"]
    classes = list(cost.coords["costs"].values)
    cost = cost.sel(costs=cost_class(classes, COST_CLASS)).to_pandas()
    cost = cost[[lt.split("::")[0] not in FOREIGN_CODES for lt in cost.index]]
    cost = cost.groupby([lt.split("::")[1] for lt in cost.index]).sum()
    return by_tech_carrier("carrier_prod"), by_tech_carrier("carrier_con"), cost


def fuel_unit_costs(prod: pd.Series, con: pd.Series, cost: pd.Series, fuels: list, iterations: int = 100) -> pd.Series:
    """Average model cost of each fuel carrier (million EUR/GWh = 1000 EUR/MWh): cost of its producers plus the cost of
    their fuel inputs (other carriers of fuels, priced the same way), divided by the amount produced. Inputs that are
    not in fuels (electricity, heat) are not added: their costs are in the other cost groups. Production is net of
    the same carrier consumed by the technology, so storage (in = out) is no producer. Producers with several outputs
    share their costs by output energy. Fixed-point iteration; a fuel nobody produces costs 0."""
    out_total = prod.groupby(level=0).sum()
    net = {(t, c): v - con.get((t, c), 0.0) for (t, c), v in prod.items()}
    unit = pd.Series(0.0, index=fuels)
    for _ in range(iterations):
        new = {}
        for fuel in fuels:
            producers = [t for (t, c), v in net.items() if c == fuel and v > 0]
            amount = sum(net[(t, fuel)] for t in producers)
            if amount <= 0:
                new[fuel] = 0.0
                continue
            total = 0.0
            for t in producers:
                share = net[(t, fuel)] / out_total[t]
                inputs = sum(v * unit[c] for (tt, c), v in con.items() if tt == t and c in unit.index and c != fuel)
                total += share * (cost.get(t, 0.0) + inputs)
            new[fuel] = total / amount
        new = pd.Series(new)
        if (new - unit).abs().max() < 1e-15:
            return new
        unit = new
    raise ValueError("fuel unit costs did not converge")


def load_power_fuel_cost(nc_path: str, plants: list, fuels: list, chp_allocation: str) -> pd.DataFrame:
    """Fuel cost of the power plants (price.fuel_power_techs) per plant and fuel: fuel consumed (GWh, from the
    results, i.e. with the plant's efficiency) x unit cost of the fuel (fuel_unit_costs), and the part allocated to
    electricity: output_share = electricity / all energy output of the plant (CHP: rest to heat), electricity = all."""
    ds = result_dataset(nc_path)
    prod, con, cost = _swiss_flows(ds)
    unit = fuel_unit_costs(prod, con, cost, fuels)
    rows = []
    for t in plants:
        out = prod[[i for i in prod.index if i[0] == t]]
        electricity = float(out.get((t, ELECTRICITY_CARRIER), 0.0))
        output = float(out.sum())
        if chp_allocation == "output_share":
            share = electricity / output if output > 0 else 0.0
        elif chp_allocation == "electricity":
            share = 1.0
        else:
            raise ValueError(f"price.chp_fuel_allocation must be output_share or electricity, got {chp_allocation!r}")
        for (tt, fuel), amount in con.items():
            if tt != t or fuel not in unit.index:
                continue
            rows.append({"tech": t, "fuel": fuel, "fuel_gwh": float(amount), "electricity_gwh": electricity,
                         "efficiency": electricity / float(amount) if amount > 0 else float("nan"),
                         "unit_cost": float(unit[fuel]), "fuel_cost": float(amount * unit[fuel]),
                         "electricity_share": share, "fuel_cost_electricity": float(amount * unit[fuel] * share)})
    return pd.DataFrame(rows, columns=["tech", "fuel", "fuel_gwh", "electricity_gwh", "efficiency", "unit_cost",
                                       "fuel_cost", "electricity_share", "fuel_cost_electricity"])


def load_scenario_scoped_cost(nc_path: str, cost_scope: str, groups: dict = None,
                              power_fuel: dict = None) -> float:
    """System cost of the price formula (price.cost_scope): total = load_scenario_system_cost; a group name of
    groups (price.cost_groups, e.g. electricity) = only the costs of that group; electricity_fuel = electricity costs
    plus the fuel costs of the power plants allocated to electricity (load_power_fuel_cost; power_fuel: keyword
    arguments plants, fuels, chp_allocation)."""
    if cost_scope == "total":
        return load_scenario_system_cost(nc_path)
    if cost_scope == "electricity_fuel":
        if not power_fuel:
            raise ValueError("price.cost_scope electricity_fuel needs price.fuel_power_techs, fuel_carriers and chp_fuel_allocation")
        return (load_scenario_scoped_cost(nc_path, "electricity", groups)
                + float(load_power_fuel_cost(nc_path, **power_fuel)["fuel_cost_electricity"].sum()))
    if not groups or cost_scope not in groups:
        raise ValueError(f"price.cost_scope must be total, electricity_fuel or one of {list(groups or {})}, got {cost_scope!r}")
    by_tech = load_scenario_cost_by_technology(nc_path, groups)
    return float(by_tech.loc[by_tech["group"] == cost_scope, "cost"].sum())


def fetch_eur_to_chf(year: int) -> tuple[float, int]:
    """Annual mean EUR/CHF exchange rate of a completed calendar year: arithmetic mean of the daily ECB
    reference rates via the Frankfurter API (time series {year}-01-01..{year}-12-31).
    Returns (mean rate, number of trading days). The API also returns the last rate before 1 January,
    so only dates within the year are used. year must be completed (< current year), otherwise
    the mean would change from run to run."""
    if year >= date.today().year:
        raise ValueError(f"EUR/CHF annual mean needs a completed year, got {year} "
                         f"(current year {date.today().year}); the mean would not be reproducible.")
    _use_certifi_certificates()
    response = requests.get(SOURCES["eur_chf_rates"].format(year=year), params={"from": "EUR", "to": "CHF"}, timeout=60)
    response.raise_for_status()
    rates = [r["CHF"] for day, r in response.json()["rates"].items() if day.startswith(f"{year}-")]
    if not rates:
        raise ValueError(f"No EUR/CHF rates returned for {year}.")
    return sum(rates) / len(rates), len(rates)


def compute_price_change(nc_path: str, elcom_ref: dict, eur_to_chf: float, cost_scale: float,
                         cost_scope: str, cost_groups: dict = None, power_fuel: dict = None) -> float:
    """Relative price change vs. the reference price (elcom_ref: ElCom values or, with cost_scope energy, p_ref and the
    energy surcharge, see scope_reference). Deliberately NOT clipped to >=0
    (unlike import) -- price is a continuous, linear attribute, so mild extrapolation beyond the
    training range (-25% to +100%, survey levels -25/0/+25/+50/+100%) is more defensible here than
    e.g. for net export.
    elcom_ref: return value of get_elcom_reference_price; eur_to_chf: rate (first element of fetch_eur_to_chf);
    cost_scale, cost_scope, cost_groups, power_fuel: price.cost_scale_factor, cost_scope, cost_groups and the power
    plant fuel settings (see load_scenario_cost_and_demand)."""
    return price_change_from_cost(*load_scenario_cost_and_demand(nc_path, cost_scale, cost_scope, cost_groups, power_fuel),
                                  elcom_ref, eur_to_chf)


def load_scenario_final_energy(nc_path: str) -> dict:
    """Final energy demand (GWh/year, carrier_con summed over time and the Swiss locations): electricity = demand_elec,
    heat = the heat demands (calliope.heat_demand_techs, delivered heat), transport = energy into the vehicles
    (technologies whose name contains calliope.transport_marker: electricity, hydrogen, diesel; the transport demand
    itself is not energy), and their sum. The model has no direct fuel demand."""
    ds = result_dataset(nc_path)
    con = ds["carrier_con"].sum("timesteps").to_pandas().abs()
    con = con[[i.split("::")[0] not in FOREIGN_CODES for i in con.index]]
    tech = pd.Series([i.split("::")[1] for i in con.index], index=con.index)
    out = {"electricity": float(con[tech == DEMAND_ELECTRICITY_TECH].sum()),
           "heat": float(con[tech.isin(HEAT_DEMAND_TECHS)].sum()),
           "transport": float(con[tech.str.contains(TRANSPORT_MARKER, regex=False) & ~tech.str.startswith(DEMAND_TECH_PREFIX)].sum())}
    out["final_energy"] = out["electricity"] + out["heat"] + out["transport"]
    return out


def _energy_reference_terms(energy_reference: dict) -> dict:
    """Price-formula constants of cost_scope energy (see scope_reference)."""
    out = {"vat": float(energy_reference.get("vat") or 0.0)}
    if energy_reference.get("reference") is not None:
        out["total_rp_kwh"] = float(energy_reference["reference"])
    surcharge = energy_reference.get("surcharge")
    if isinstance(surcharge, dict):
        out["taxes_levies_rp_kwh"], out["netznutzung_rp_kwh"] = 0.0, 0.0
        out.update({f"surcharge_rate_{c}": float(r) for c, r in surcharge.items()})
    elif surcharge is not None:
        out["taxes_levies_rp_kwh"], out["netznutzung_rp_kwh"] = float(surcharge), 0.0
    return out


def scope_reference(ref: dict, cost_scope: str, energy_reference: dict, margin: float) -> dict:
    """Constants of the price formula: the ElCom reference values plus the revenue margin (price.margin, key margin)
    and the VAT rate (key vat, 0 outside cost_scope energy). With cost_scope energy, energy_reference = {"reference":
    p_ref, "surcharge": tau + g, "vat": rate} (price.energy_reference_ct_per_kwh, the entry price.energy_surcharge of
    price.energy_surcharges, price.energy_vat): a number replaces the reference price total_rp_kwh; a number as
    surcharge replaces taxes/levies + grid usage (taxes_levies_rp_kwh = surcharge, grid usage 0), a dict carrier ->
    Rp./kWh gives the rates per end-use carrier (keys surcharge_rate_<carrier>, see simulated_price); null keeps the
    ElCom electricity values. Other cost scopes: ElCom values unchanged."""
    out = {**ref, "margin": float(margin), "vat": 0.0}
    if cost_scope != "energy" or not energy_reference:
        return out
    return {**out, **_energy_reference_terms(energy_reference)}


def scope_reference_table(elcom: pd.DataFrame, cost_scope: str, energy_reference: dict, margin: float) -> pd.DataFrame:
    """scope_reference for the regional ElCom table (index region): the same values in every region."""
    out = elcom.assign(margin=float(margin), vat=0.0)
    if cost_scope != "energy" or not energy_reference:
        return out
    return out.assign(**_energy_reference_terms(energy_reference))


def price_reference_columns(table: pd.DataFrame) -> list[str]:
    """Columns of a scope_reference_table that enter the price formula."""
    return [c for c in table.columns if c in ("total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh", "margin", "vat")
            or c.startswith("surcharge_rate_")]


def load_scenario_end_use(nc_path: str) -> dict:
    """End-use consumption per carrier (GWh/year, carrier_con at the Swiss locations) of the technologies in
    price.end_use_techs, for the taxes and levies per carrier (simulated_price)."""
    ds = result_dataset(nc_path)
    con = ds["carrier_con"].sum("timesteps").to_pandas().abs()
    con = con[[i.split("::")[0] not in FOREIGN_CODES for i in con.index]]
    parts = [i.split("::") for i in con.index]
    return {name: float(con[[p[1] in spec["techs"] and p[2] == spec["carrier"] for p in parts]].sum())
            for name, spec in END_USE_TECHS.items()}


def load_scenario_cost_and_demand(nc_path: str, cost_scale: float, cost_scope: str,
                                  cost_groups: dict = None, power_fuel: dict = None) -> tuple[float, float, dict]:
    """Swiss system cost (million EUR/year; all technologies, or with cost_scope only one cost group, see
    load_scenario_scoped_cost) times cost_scale (price.cost_scale_factor, 1.0 = costs as in the result file),
    national electricity demand (GWh) and None, the scenario inputs of price_change_from_cost.
    cost_scope energy: all costs over the final energy demand (load_scenario_final_energy) instead of electricity,
    and the end-use consumption per carrier (load_scenario_end_use) for taxes and levies per carrier."""
    if cost_scope == "energy":
        return (cost_scale * load_scenario_system_cost(nc_path), load_scenario_final_energy(nc_path)["final_energy"],
                load_scenario_end_use(nc_path))
    return (cost_scale * load_scenario_scoped_cost(nc_path, cost_scope, cost_groups, power_fuel),
            aggregate_national(load_scenario_demand(nc_path), "demand_gwh"), None)


def price_surcharge(demand: float, elcom_ref: dict, end_use: dict = None) -> float:
    """Taxes/levies + grid usage tau + g (Rp./kWh of demand): taxes_levies_rp_kwh + netznutzung_rp_kwh, or with
    rates per carrier (keys surcharge_rate_<carrier>, scope_reference) sum(rate * end-use GWh) / demand."""
    rates = {k[len("surcharge_rate_"):]: v for k, v in elcom_ref.items() if k.startswith("surcharge_rate_")}
    if not rates:
        return elcom_ref["taxes_levies_rp_kwh"] + elcom_ref["netznutzung_rp_kwh"]
    if end_use is None:
        raise ValueError("taxes and levies per carrier need the end-use consumption (cost_scope energy)")
    return sum(r * end_use[c] for c, r in rates.items()) / demand


def simulated_price(system_cost: float, demand: float, elcom_ref: dict, eur_to_chf: float, end_use: dict = None) -> float:
    """Simulated price p_sim (Rp./kWh) = (C/D * e * 100 * (1 + margin) + tau + g) * (1 + VAT); elcom_ref: return value
    of scope_reference (reference values, margin, VAT rate, rates per carrier); tau + g see price_surcharge."""
    cost_per_kwh_chf = (system_cost / demand) * eur_to_chf
    simulated_rp_kwh = cost_per_kwh_chf * 100 * (1 + elcom_ref["margin"])
    # Grid usage (distribution grid) is not included in the Calliope system cost -> constant surcharge
    simulated_rp_kwh += price_surcharge(demand, elcom_ref, end_use)
    return simulated_rp_kwh * (1 + elcom_ref["vat"])


def price_change_from_cost(system_cost: float, demand: float, end_use: dict, elcom_ref: dict, eur_to_chf: float) -> float:
    """Price-change formula of compute_price_change for already loaded system cost, demand and end-use consumption
    (load_scenario_cost_and_demand), so that several reference prices / rates can be evaluated without re-reading the
    scenario file."""
    simulated_rp_kwh = simulated_price(system_cost, demand, elcom_ref, eur_to_chf, end_use)
    return (simulated_rp_kwh - elcom_ref["total_rp_kwh"]) / elcom_ref["total_rp_kwh"]


def national_area_km2(capacity_df: pd.DataFrame, area_dict: dict) -> float:
    """Area of Switzerland as the sum over the scenario's Swiss locations (Calliope cantons, incl. the
    merged codes AI_AR, BL_BS, NW_OW). Checked against the sum of the individual cantons in the canton
    CSV, so that a missing or double-counted location is caught."""
    locations = capacity_df["canton"].unique()
    total = sum(area_dict[c] for c in locations)
    csv_total = sum(v for c, v in area_dict.items() if c not in CANTON_MERGES)
    if not np.isclose(total, csv_total):
        raise ValueError(f"Area of the scenario's locations ({total} km²) does not match the canton CSV "
                         f"({csv_total} km²); locations: {sorted(locations)}")
    return total


def compute_national_relative_land(nc_path: str, area_dict: dict) -> float:
    """Relative land use as a share of the national area (main definition, land.definition =
    national_share): national land use (sum of land_use_km2 over all Swiss locations) divided by the
    national area (national_area_km2). The survey attribute is a share of the country's land, and all
    other attributes are national as well. A regional variant (land use per language region) is
    deliberately not implemented, because all other attributes are national."""
    capacity_df = load_scenario_capacity(nc_path)
    land_df = compute_land_from_capacity(capacity_df, area_dict)
    return land_df["land_use_km2"].sum() / national_area_km2(capacity_df, area_dict)


def compute_mean_canton_relative_land(nc_path: str, area_dict: dict) -> float:
    """Previous definition (land.definition = canton_mean): unweighted mean over the cantons of
    land_use_km2 / canton area. Unlike compute_national_relative_land, every canton counts equally
    regardless of its size, so small cantons with much land use weigh as much as large ones (values
    are about twice the national share for most scenarios). Kept for comparison."""
    capacity_df = load_scenario_capacity(nc_path)
    land_df = compute_land_from_capacity(capacity_df, area_dict)
    per_canton_land = land_df.groupby("canton")["land_use_km2"].sum()
    per_canton_area = land_df.groupby("canton")["canton_area_km2"].first()
    return (per_canton_land / per_canton_area).mean()


# land.definition in config/default.yaml -> function computing relative_land
RELATIVE_LAND_DEFINITIONS = {
    "national_share": compute_national_relative_land,
    "canton_mean": compute_mean_canton_relative_land,
}


def electricity_producing_technologies(nc_path: str) -> list[str]:
    """Technologies that can produce electricity at the Swiss locations (loc_tech_carriers_prod with carrier
    electricity, without the transmission links tech:<region>), from the coordinates of the result file."""
    ds = result_dataset(nc_path)
    entries = [c.split("::") for c in ds.coords["loc_tech_carriers_prod"].values]
    return sorted({tech for loc, tech, carrier in entries
                   if loc not in FOREIGN_CODES and ":" not in tech and carrier == ELECTRICITY_CARRIER})


def check_attribute_mappings(nc_path: str) -> None:
    """Every electricity producer of the scenario is in the ownership and the source mapping or deliberately excluded
    (checks.check_technology_mapping); stops otherwise."""
    check_technology_mapping(electricity_producing_technologies(nc_path), {
        "ownership mapping": (OWNERSHIP_MAPPING, OWNERSHIP_EXCLUDED_TECHS),
        "source mapping (incl. PV reference)": (list(TECH_SOURCE_MAPPING) + PV_REFERENCE_TECHS, SOURCE_EXCLUDED_TECHS),
    }, nc_path)


def national_import_share(nc_path: str, imports: dict) -> float:
    """Import attribute of the national aggregate with the definition of the main analysis (imports: definition,
    denominator, fuel_techs, diesel_techs of imports in config/default.yaml): import_quantities, as rule import_shares
    for the regional analysis; the definition electricity is the net electricity import over the electricity
    consumption (compute_import_share), as the regional analysis uses it for this definition."""
    if imports["definition"] == "electricity":
        return compute_import_share(nc_path)
    quantities = import_quantities(nc_path, imports["fuel_techs"], imports["diesel_techs"], imports["denominator"])
    return quantities[f"import_share_{imports['definition']}"]


def compute_all_attributes(scenario_id: str, nc_path: str, area_dict: dict, elcom_ref: dict, eur_to_chf: float,
                           land_definition: str, cost_scale: float, cost_scope: str, imports: dict,
                           cost_groups: dict = None, power_fuel: dict = None) -> dict:
    """Computes all 11 choice-model attributes (national) for one scenario.
    scenario_id: the scenario's ID in config/default.yaml (scenarios), for the cost change of Mellot Table 3;
    land_definition: key of RELATIVE_LAND_DEFINITIONS (land.definition in config/default.yaml); imports: import
    definition of the main analysis (national_import_share);
    cost_scale, cost_scope, cost_groups, power_fuel: price.cost_scale_factor, cost_scope, cost_groups, power plant fuels."""
    if land_definition not in RELATIVE_LAND_DEFINITIONS:
        raise ValueError(f"Unknown land definition {land_definition!r}, expected one of {list(RELATIVE_LAND_DEFINITIONS)}")
    check_attribute_mappings(nc_path)
    capacity_df = load_scenario_capacity(nc_path)
    return {
        # Empirically verified, not a placeholder: the CH-foreign AC capacity is identical in all 12
        # scenarios (13.249 GW per direction); Mellot et al. do not expand transmission.
        "transmission_change": TRANSMISSION_CHANGE,
        "relative_land": RELATIVE_LAND_DEFINITIONS[land_definition](nc_path, area_dict),
        "import_share": national_import_share(nc_path, imports),
        **compute_ownership_shares(capacity_df),
        **compute_technology_mix_shares(capacity_df),
        "price_change": compute_price_change(nc_path, elcom_ref=elcom_ref, eur_to_chf=eur_to_chf, cost_scale=cost_scale,
                                             cost_scope=cost_scope, cost_groups=cost_groups, power_fuel=power_fuel),
        # Official cost change vs. EP2050+ (Mellot Table 3), not a choice-model attribute;
        # for comparing preference rank vs. cost rank (NaN for baseline, not in Table 3); by the scenario ID of the
        # configuration, not the file name (the EP2050+ files of 2017/2018 are named barrier_baseline,...)
        "mellot_cost_change_pct": MELLOT_COST_CHANGE_PCT[scenario_id],
    }
