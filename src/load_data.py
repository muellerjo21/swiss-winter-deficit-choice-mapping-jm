"""
Load and extract fitted coefficients from Tröndle, Mey & Lilliestam's (2025)
discrete choice model.

The pipeline uses choice-model-jan-2026.nc (CHOICE_MODEL_PATH): 11 attributes, fitted per
language region (country coord: DA/DE/DE-CH/EN/FR/FR-CH/PL/PT/SO/SV). For Switzerland, select
DE-CH or FR-CH per canton via CANTON_LANGUAGE -- there is no generic "Switzerland" or
"NOT_SAMPLED" level here. The older published-paper model (6 attributes, per country) is only
used by the unmaintained first approach in legacy/.

See the project proposal for background on the model.
"""

import os
import re
from datetime import date
import ssl, certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
import arviz as az
import numpy as np
import pandas as pd
import requests
import xarray as xr
from SPARQLWrapper import SPARQLWrapper, JSON

from config import (
    CANTON_LANGUAGE, FOREIGN_CODES, CANTON_NAME_TO_CODE, CANTON_MERGES,
    CAPACITY_DENSITY_GW_PER_KM2, OWNERSHIP_MAPPING, PRICE_MARGIN, PRICE_REFERENCE_YEAR, PRICE_CATEGORY,
    TECH_SOURCE_MAPPING, PV_REFERENCE_TECHS, TRANSMISSION_REFERENCE_YEAR, CHOICE_MODEL_PATH,
    SECTOR_COUPLING_ELEC_TECHS, SCENARIO_DIR, CANTON_AREA_CSV_PATH, RAW_DIR, PROCESSED_DIR,
    MELLOT_COST_CHANGE_PCT,
)


def load_beta_partworths_mean(data_path, country: str) -> pd.DataFrame:
    """
    Load the fitted choice model and extract posterior-MEAN beta values
    for one country/region (a single point estimate per attribute).

    Parameters
    ----------
    data_path : str or Path
        Path to the .nc file (CHOICE_MODEL_PATH, or legacy_config.DATA_PATH).
    country : str
        Which level of the model's `country` coordinate to select.
        For CHOICE_MODEL_PATH: one of DA/DE/DE-CH/EN/FR/FR-CH/PL/PT/SO/SV.
        For legacy_config.DATA_PATH: one of DNK/DEU/PRT/POL/NOT_SAMPLED.
        No default on purpose -- the valid values differ between the two files,
        so picking a wrong implicit default silently gives the wrong region.

    Use this for a first, quick pass (fixed betas). See
    `load_beta_partworths_samples` for the full posterior, needed for
    uncertainty quantification (credible intervals on utility/ranking).

    Returns
    -------
    pd.DataFrame with columns: attribute, beta_mean
    """
    idata = az.from_netcdf(data_path)
    beta = idata.posterior["beta_partworths"].sel(country=country)
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
        Path to the .nc file (CHOICE_MODEL_PATH, or legacy_config.DATA_PATH).
    country : str
        See `load_beta_partworths_mean` for valid values per file.

    Returns
    -------
    dict[str, np.ndarray]
        Keys are attribute labels. For CHOICE_MODEL_PATH these are the 11 fitted
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
    beta = idata.posterior["beta_partworths"].sel(country=country)

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
    with m=1 (constant_data/m) in the Jan 2026 model (CHOICE_MODEL_PATH):
        u = x_scaled . (beta_partworths[country] + m * mobile_partworths)
    verified against u_left/u_right in the posterior. Not region-specific (no country dim).
    The reading "m=1 = answered on a mobile device" rests on the variable name only; the
    file contains no further documentation of m.

    Returns
    -------
    pd.DataFrame with columns: attribute, mobile_mean
    """
    idata = az.from_netcdf(data_path)
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
    mobile_stacked = idata.posterior["mobile_partworths"].stack(sample=("chain", "draw"))
    return {attr: mobile_stacked.sel(attribute=attr).values
            for attr in mobile_stacked.coords["attribute"].values}


#not in the pipeline
def load_scenarios(scenarios_path: str) -> pd.DataFrame:
    """
    Load the scenarios CSV file, which contains the attribute values for
    each scenario to be evaluated.
    """
    df = pd.read_csv(scenarios_path)
    return df


#not in the pipeline
def compute_beta_real_units(idata) -> pd.DataFrame:
    """Scale full posterior beta_partworths to real units (beta / max_survey_value)."""
    beta = idata.posterior["beta_partworths"]

    raw_left = idata.constant_data["attribute_values_left"]
    raw_right = idata.constant_data["attribute_values_right"]
    max_per_attribute = xr.concat([raw_left, raw_right], dim="choice_situation").max(dim="choice_situation")

    beta_real = beta / max_per_attribute

    return beta_real.to_dataframe(name="beta_real").reset_index()


def _load_loc_tech_variable(nc_path: str, variable: str, value_name: str) -> pd.DataFrame:
    """Load a Calliope loc_tech-indexed variable, split into canton/tech, add language region."""
    ds = xr.open_dataset(nc_path)
    values = ds[variable].to_pandas()
    values.index = values.index.str.split("::", expand=True)
    values.index.names = ["canton", "tech"]
    values = values.reset_index(name=value_name)
    values["language_region"] = values["canton"].map(CANTON_LANGUAGE)
    return values


def load_scenario_capacity(nc_path: str) -> pd.DataFrame:
    df = _load_loc_tech_variable(nc_path, "energy_cap", "capacity")
    return df[~df["canton"].isin(FOREIGN_CODES)].copy()


#not in the pipeline
def load_scenario_land(nc_path: str) -> pd.DataFrame:
    df = _load_loc_tech_variable(nc_path, "resource_area", "land_use_km2")
    return df[~df["canton"].isin(FOREIGN_CODES)].copy()


#not in the pipeline
def get_ch_foreign_transmission_techs(ds) -> list[str]:
    """Return loc_techs for AC transmission lines between Switzerland and a neighbouring country."""
    all_transmission = ds.coords["loc_techs_transmission"].values
    ch_foreign = []
    for t in all_transmission:
        if "ac_transmission" not in t:
            continue
        origin, _, dest = t.partition("::")
        tech, _, dest_canton = dest.partition(":")
        if (origin in FOREIGN_CODES) != (dest_canton in FOREIGN_CODES):
            ch_foreign.append(t)
    return ch_foreign

#not in the pipeline
def load_scenario_transmission_capacity(nc_path: str) -> pd.DataFrame:
    """Load installed capacity of CH-foreign AC transmission lines."""
    ds = xr.open_dataset(nc_path)
    ch_foreign = get_ch_foreign_transmission_techs(ds)
    cap = ds["energy_cap"].to_pandas()
    ds.close()
    cap = cap.loc[cap.index.isin(ch_foreign)]
    return cap.reset_index().rename(columns={"loc_techs": "loc_tech", "energy_cap": "capacity"})


def get_ch_import_carrier_techs(ds) -> list[str]:
    """loc_tech_carriers_prod entries with a Swiss canton as origin and a foreign country as
    destination -> carrier_prod on these = import into Switzerland."""
    prod_coords = ds.coords["loc_tech_carriers_prod"].values
    result = []
    for c in prod_coords:
        origin, _, rest = c.partition("::")
        if "ac_transmission" not in rest:
            continue
        dest = rest.partition(":")[2].partition("::")[0]
        if origin not in FOREIGN_CODES and dest in FOREIGN_CODES:
            result.append(c)
    return result


#not in the pipeline
def load_scenario_import(nc_path) -> pd.DataFrame:
    ds = xr.open_dataset(nc_path)
    import_techs = get_ch_import_carrier_techs(ds)
    imports = (
        ds["carrier_prod"]
        .sel(loc_tech_carriers_prod=import_techs)
        .sum(dim="timesteps")
        .to_pandas()
        .rename("import_mwh")
        .reset_index()
    )
    ds.close()

    imports[["canton", "tech_carrier"]] = imports["loc_tech_carriers_prod"].str.split("::", n=1, expand=True)
    imports["language_region"] = imports["canton"].map(CANTON_LANGUAGE)
    return imports


def aggregate_national(df: pd.DataFrame, value_col: str) -> float:
    """Sums an attribute column over all cantons into one national value."""
    return df[value_col].sum()


#not in the pipeline
def get_ch_fuel_import_techs(ds) -> list[str]:
    """loc_tech_carriers_prod entries for all fuel import technologies at Swiss locations
    (e.g. import_syndiesel, import_synmethane, import_hydrogen -- varies by scenario)."""
    prod_coords = ds.coords["loc_tech_carriers_prod"].values
    result = []
    for c in prod_coords:
        canton, sep, rest = c.partition("::")
        if not sep or canton in FOREIGN_CODES:
            continue
        if rest.startswith("import_") and "ac_transmission" not in rest:
            result.append(c)
    return result


#not in the pipeline
def load_scenario_fuel_import(nc_path: str) -> pd.DataFrame:
    ds = xr.open_dataset(nc_path)
    fuel_techs = get_ch_fuel_import_techs(ds)
    fuel = (
        ds["carrier_prod"]
        .sel(loc_tech_carriers_prod=fuel_techs)
        .sum(dim="timesteps")
        .to_pandas()
        .rename("fuel_import_gwh")
        .reset_index()
    )
    ds.close()

    fuel[["canton", "tech_carrier"]] = fuel["loc_tech_carriers_prod"].str.split("::", n=1, expand=True)
    fuel["language_region"] = fuel["canton"].map(CANTON_LANGUAGE)
    return fuel


def scenario_id_from_filename(filename: str) -> str:
    """Extracts a short, readable scenario ID from the file name."""
    base = filename.removesuffix(".nc")
    return base.split(",")[0].replace("barrier_", "")


#not in the pipeline
def extract_all_scenarios(scenario_dir: str = SCENARIO_DIR) -> dict[str, pd.DataFrame]:
    """Loops over all scenario files and extracts all attributes.
    Returns a dict of DataFrames, one per attribute, with a scenario_id column."""
    results = {
        "capacity": [], "land": [], "transmission_capacity": [],
        "import": [], "fuel_import": [],
    }

    for filename in sorted(os.listdir(scenario_dir)):
        if not filename.endswith(".nc"):
            continue
        nc_path = os.path.join(scenario_dir, filename)
        sid = scenario_id_from_filename(filename)
        print(f"Processing {sid}...")

        cap = load_scenario_capacity(nc_path); cap["scenario_id"] = sid
        land = load_scenario_land(nc_path); land["scenario_id"] = sid
        trans = load_scenario_transmission_capacity(nc_path); trans["scenario_id"] = sid
        imp = load_scenario_import(nc_path); imp["scenario_id"] = sid
        fuel = load_scenario_fuel_import(nc_path); fuel["scenario_id"] = sid

        results["capacity"].append(cap)
        results["land"].append(land)
        results["transmission_capacity"].append(trans)
        results["import"].append(imp)
        results["fuel_import"].append(fuel)

    return {k: pd.concat(v, ignore_index=True) for k, v in results.items()}


#not in the pipeline
def save_all_scenarios(scenario_dir: str = SCENARIO_DIR, out_dir: str = PROCESSED_DIR) -> None:
    os.makedirs(out_dir, exist_ok=True)
    all_data = extract_all_scenarios(scenario_dir)
    for name, df in all_data.items():
        df.to_csv(os.path.join(out_dir, f"scenario_{name}.csv"), index=False)
        print(f"Saved {name}: {len(df)} rows")


def load_canton_area(csv_path: str = CANTON_AREA_CSV_PATH) -> dict:
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


#not in the pipeline
def compute_relative_land(land_df: pd.DataFrame, area_dict: dict) -> pd.DataFrame:
    """Computes relative land use (land_use_km2 / canton area) per canton/technology,
    matching the scale of the choice-model attribute LAND."""
    land_df = land_df.copy()
    land_df["canton_area_km2"] = land_df["canton"].map(area_dict)
    land_df["relative_land"] = land_df["land_use_km2"] / land_df["canton_area_km2"]
    return land_df


def compute_land_from_capacity(capacity_df: pd.DataFrame, area_dict: dict, density_dict: dict = CAPACITY_DENSITY_GW_PER_KM2) -> pd.DataFrame:
    """Computes land use from installed capacity via technology-specific capacity density
    (MW/km²), following Tröndle et al.'s methodology (8 MW/km² wind, 80 MW/km² PV)."""
    df = capacity_df[capacity_df["tech"].isin(density_dict.keys())].copy()
    df["density_mw_per_km2"] = df["tech"].map(density_dict)
    df["land_use_km2"] = df["capacity"] / df["density_mw_per_km2"]
    df["canton_area_km2"] = df["canton"].map(area_dict)
    df["relative_land"] = df["land_use_km2"] / df["canton_area_km2"]
    return df


def load_scenario_net_import(nc_path: str) -> pd.DataFrame:
    """Net electricity import (import - export) per Swiss cross-border line, in GWh."""
    ds = xr.open_dataset(nc_path)
    import_techs = get_ch_import_carrier_techs(ds)

    imp = ds["carrier_prod"].sel(loc_tech_carriers_prod=import_techs).sum(dim="timesteps")
    exp = ds["carrier_con"].sel(loc_tech_carriers_con=import_techs).sum(dim="timesteps")
    ds.close()

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
    return [c for c in con_coords if "::demand_elec::" in c and c.split("::")[0] not in FOREIGN_CODES]


def get_ch_total_electricity_demand_techs(ds) -> list[str]:
    """demand_elec plus electricity consumption from sector coupling (SECTOR_COUPLING_ELEC_TECHS) at
    Swiss locations. Storage (pumped_hydro, hydrogen_electricity_storage, battery) deliberately
    excluded -- stored electricity is released again later and would be counted twice."""
    con_coords = ds.coords["loc_tech_carriers_con"].values
    sector_coupling = [
        c for c in con_coords
        if c.split("::")[0] not in FOREIGN_CODES
        and c.split("::")[1] in SECTOR_COUPLING_ELEC_TECHS
        and c.endswith("::electricity")
    ]
    return get_ch_demand_elec_techs(ds) + sector_coupling


def load_scenario_demand(nc_path: str) -> pd.DataFrame:
    """Total electricity consumption per Swiss canton and tech (demand_elec + sector coupling), in GWh."""
    ds = xr.open_dataset(nc_path)
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
    ds.close()
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


#not in the pipeline
def compute_import_share_extended(nc_path: str) -> float:
    """Extended import share = (electricity net import + fuel import) / total consumption (electricity).
    Own extension beyond the original choice-model definition (which covers electricity only)."""
    net_import = aggregate_national(load_scenario_net_import(nc_path), "net_import_gwh")
    fuel_import = aggregate_national(load_scenario_fuel_import(nc_path), "fuel_import_gwh")
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    share = (net_import + fuel_import) / demand
    return max(0.0, min(1.0, share))


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


def compute_technology_mix_shares(capacity_df: pd.DataFrame, mapping: dict = TECH_SOURCE_MAPPING) -> dict:
    """Capacity share per source_* category. The denominator (total_capacity) includes ALL
    generation-relevant technologies incl. the PV reference category (PV_REFERENCE_TECHS);
    otherwise leaving out PV capacity would artificially shrink the denominator and overstate all shares."""
    relevant_techs = list(mapping.keys()) + PV_REFERENCE_TECHS
    df = capacity_df[capacity_df["tech"].isin(relevant_techs)].copy()
    df["source_category"] = df["tech"].map(mapping)
    total_capacity = df["capacity"].sum()
    shares = df.groupby("source_category")["capacity"].sum() / total_capacity
    return {
        "source_wind": shares.get("source_wind", 0.0),
        "source_gas": shares.get("source_gas", 0.0),
        "source_biomass": shares.get("source_biomass", 0.0),
        "source_coal": 0.0,
        "source_nuclear": 0.0,
    }


ELCOM_SPARQL_ENDPOINT = "https://lindas.admin.ch/query"


def fetch_elcom_price(year: int, category: str, product: str = "standard") -> pd.DataFrame:
    """Fetches ElCom electricity prices (Rp./kWh) per municipality directly via the LINDAS SPARQL
    endpoint instead of hard-coding values. category e.g. 'H4' = standard household category
    (PRICE_CATEGORY, i.e. price.category in config/default.yaml)."""
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


def get_elcom_reference_price(year: int, category: str) -> dict:
    """National median electricity price and the taxes/levies component, directly from ElCom via
    LINDAS (no hard-coding). Returned in Rp./kWh."""
    df = fetch_elcom_price(year, category)
    return {
        "total_rp_kwh": df["total"].median(),
        "taxes_levies_rp_kwh": (df["charge"] + df["aidfee"]).median(),
        "netznutzung_rp_kwh": df["grid"].median(),
    }


def load_scenario_system_cost(nc_path: str) -> float:
    """Total Swiss system cost (million EUR/year), summed over all Swiss loc_techs
    (foreign loc_techs excluded, as for the other attributes)."""
    ds = xr.open_dataset(nc_path)
    cost = ds["cost"]
    classes = list(cost.coords["costs"].values)
    cost = cost.sel(costs="monetary") if "monetary" in classes else cost.sel(costs=classes[0])
    loc_techs = cost.coords["loc_techs_cost"].values
    ch_loc_techs = [lt for lt in loc_techs if lt.split("::")[0] not in FOREIGN_CODES]
    total = cost.sel(loc_techs_cost=ch_loc_techs).sum().item()
    ds.close()
    return total  # million EUR/year


def fetch_eur_to_chf(year: int) -> tuple[float, int]:
    """Annual mean EUR/CHF exchange rate of a completed calendar year: arithmetic mean of the daily ECB
    reference rates via the Frankfurter API (time series {year}-01-01..{year}-12-31).
    Returns (mean rate, number of trading days). The API also returns the last rate before 1 January,
    so only dates within the year are used. year must be completed (< current year), otherwise
    the mean would change from run to run."""
    if year >= date.today().year:
        raise ValueError(f"EUR/CHF annual mean needs a completed year, got {year} "
                         f"(current year {date.today().year}); the mean would not be reproducible.")
    response = requests.get(f"https://api.frankfurter.dev/v1/{year}-01-01..{year}-12-31",
                            params={"from": "EUR", "to": "CHF"})
    response.raise_for_status()
    rates = [r["CHF"] for day, r in response.json()["rates"].items() if day.startswith(f"{year}-")]
    if not rates:
        raise ValueError(f"No EUR/CHF rates returned for {year}.")
    return sum(rates) / len(rates), len(rates)


def compute_price_change(nc_path: str, elcom_ref: dict, eur_to_chf: float) -> float:
    """Relative price change vs. the ElCom reference price. Deliberately NOT clipped to >=0
    (unlike import) -- price is a continuous, linear attribute, so mild extrapolation beyond the
    training range (-25% to +100%, survey levels -25/0/+25/+50/+100%) is more defensible here than
    e.g. for net export.
    elcom_ref: return value of get_elcom_reference_price; eur_to_chf: return value of fetch_eur_to_chf."""
    system_cost = load_scenario_system_cost(nc_path)
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    cost_per_kwh_chf = (system_cost / demand) * eur_to_chf
    simulated_rp_kwh = cost_per_kwh_chf * 100 * (1 + PRICE_MARGIN)
    # Grid usage (distribution grid) is not included in the Calliope system cost -> constant surcharge
    simulated_rp_kwh += elcom_ref["taxes_levies_rp_kwh"] + elcom_ref["netznutzung_rp_kwh"]
    return (simulated_rp_kwh - elcom_ref["total_rp_kwh"]) / elcom_ref["total_rp_kwh"]


def compute_national_relative_land(nc_path: str, area_dict: dict) -> float:
    """National average of relative land use (unweighted mean over cantons).
    For a later regional application of the model, the canton values are needed separately
    (compute_land_from_capacity provides them at that granularity)."""
    capacity_df = load_scenario_capacity(nc_path)
    land_df = compute_land_from_capacity(capacity_df, area_dict)
    per_canton_land = land_df.groupby("canton")["land_use_km2"].sum()
    per_canton_area = land_df.groupby("canton")["canton_area_km2"].first()
    return (per_canton_land / per_canton_area).mean()


def compute_all_attributes(nc_path: str, area_dict: dict, elcom_ref: dict, eur_to_chf: float) -> dict:
    """Computes all 11 choice-model attributes (national) for one scenario."""
    capacity_df = load_scenario_capacity(nc_path)
    return {
        # Empirically verified, not a placeholder: the CH-foreign AC capacity is identical in all 12
        # scenarios (13.249 GW per direction); Mellot et al. do not expand transmission.
        "transmission_change": 0.0,
        "relative_land": compute_national_relative_land(nc_path, area_dict),
        # import_share_extended (compute_import_share_extended) deliberately not included:
        # fuel and electricity GWh are not comparable; the choice model defines electricity import only.
        "import_share": compute_import_share(nc_path),
        **compute_ownership_shares(capacity_df),
        **compute_technology_mix_shares(capacity_df),
        "price_change": compute_price_change(nc_path, elcom_ref=elcom_ref, eur_to_chf=eur_to_chf),
        # Official cost change vs. EP2050+ (Mellot Table 3), not a choice-model attribute;
        # for comparing preference rank vs. cost rank (NaN for baseline, not in Table 3)
        "mellot_cost_change_pct": MELLOT_COST_CHANGE_PCT[scenario_id_from_filename(os.path.basename(nc_path))],
    }


#not in the pipeline
def compute_all_scenarios(scenario_dir: str = SCENARIO_DIR, area_csv_path: str = CANTON_AREA_CSV_PATH) -> pd.DataFrame:
    """Runs all finished attribute functions over all scenario files; the ElCom reference price and
    the EUR/CHF rate are fetched once (not per scenario) and reused."""
    area_dict = load_canton_area(area_csv_path)
    elcom_ref = get_elcom_reference_price(PRICE_REFERENCE_YEAR, PRICE_CATEGORY)
    eur_to_chf, _ = fetch_eur_to_chf(PRICE_REFERENCE_YEAR)

    rows = []
    for filename in sorted(os.listdir(scenario_dir)):
        if not filename.endswith(".nc"):
            continue
        nc_path = os.path.join(scenario_dir, filename)
        sid = scenario_id_from_filename(filename)
        print(f"Processing {sid}...")
        row = compute_all_attributes(nc_path, area_dict, elcom_ref, eur_to_chf)
        row["scenario_id"] = sid
        rows.append(row)
    return pd.DataFrame(rows)


SWISSGRID_LISTING_URL = "https://www.swissgrid.ch/en/home/customers/topics/energy-data-ch.html"


#not in the pipeline
def get_swissgrid_report_url(year: int) -> str:
    """Dynamically finds the Swissgrid download URL for a given year (instead of hard-coding the
    year->URL mapping -- the URLs contain an asset ID that cannot be derived from the year).
    NOTE: this file only contains national production/consumption statistics, no cross-border
    capacities -- so it is not directly usable for transmission (see notes)."""
    response = requests.get(SWISSGRID_LISTING_URL)
    response.raise_for_status()
    match = re.search(
        rf'(https://www\.swissgrid\.ch/dam/jcr:[a-f0-9-]+/EnergieUebersichtCH-{year}\.xlsx)',
        response.text,
    )
    if not match:
        raise ValueError(f"No Swissgrid report URL found for {year}.")
    return match.group(1)


#not in the pipeline
def download_swissgrid_report(year: int = TRANSMISSION_REFERENCE_YEAR, out_dir: str = RAW_DIR) -> str:
    """Downloads the Swissgrid annual report for a given year and saves it locally."""
    url = get_swissgrid_report_url(year)
    response = requests.get(url)
    response.raise_for_status()
    out_path = os.path.join(out_dir, f"EnergieUebersichtCH-{year}.xlsx")
    with open(out_path, "wb") as f:
        f.write(response.content)
    return out_path


if __name__ == "__main__":
    print("=== Mean betas (point estimate, DE-CH) ===")
    print(load_beta_partworths_mean(CHOICE_MODEL_PATH, country="DE-CH"))

    print()
    print("=== Sample betas (full posterior, DE-CH) ===")
    samples = load_beta_partworths_samples(CHOICE_MODEL_PATH, country="DE-CH")
    for attr, values in samples.items():
        print(f"{attr}: {len(values)} samples, mean={values.mean():.4f}, "
              f"94% HDI=[{np.percentile(values, 3):.4f}, {np.percentile(values, 97):.4f}]")

    print()
    print("=== Extracting all scenario data ===")
    save_all_scenarios()