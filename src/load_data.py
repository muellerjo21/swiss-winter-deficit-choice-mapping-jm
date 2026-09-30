"""
Load and extract fitted coefficients from Tröndle, Mey & Lilliestam's (2025)
discrete choice model.

Two model files exist:
- choice-model-jan-2026.nc (CHOICE_MODEL_PATH): the current model used throughout this
  pipeline. 11 attributes, fitted per language region (country coord:
  DA/DE/DE-CH/EN/FR/FR-CH/PL/PT/SO/SV). For Switzerland, select DE-CH or FR-CH per canton
  via CANTON_LANGUAGE -- there is no generic "Switzerland" or "NOT_SAMPLED" level here.
- choice-model-inference.nc (DATA_PATH): Tim's original published-paper model. 6 attributes,
  fitted per country (country coord: DNK/DEU/PRT/POL/NOT_SAMPLED). Only used by
  choice_model.py / 02_single_scenario.ipynb.

See CLAUDE.md and the project proposal for background on the model.
"""

import os
import re
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
    CAPACITY_DENSITY_GW_PER_KM2, OWNERSHIP_MAPPING, PRICE_MARGIN, PRICE_REFERENCE_YEAR,
    TECH_SOURCE_MAPPING, PV_REFERENCE_TECHS, TRANSMISSION_REFERENCE_YEAR, CHOICE_MODEL_PATH,
    SECTOR_COUPLING_ELEC_TECHS,
)


def load_beta_partworths_mean(data_path, country: str) -> pd.DataFrame:
    """
    Load the fitted choice model and extract posterior-MEAN beta values
    for one country/region (a single point estimate per attribute).

    Parameters
    ----------
    data_path : str or Path
        Path to the .nc file (CHOICE_MODEL_PATH or DATA_PATH).
    country : str
        Which level of the model's `country` coordinate to select.
        For CHOICE_MODEL_PATH: one of DA/DE/DE-CH/EN/FR/FR-CH/PL/PT/SO/SV.
        For DATA_PATH: one of DNK/DEU/PRT/POL/NOT_SAMPLED.
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
        Path to the .nc file (CHOICE_MODEL_PATH or DATA_PATH).
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


def load_scenarios(scenarios_path: str) -> pd.DataFrame:
    """
    Load the scenarios CSV file, which contains the attribute values for
    each scenario to be evaluated.
    """
    df = pd.read_csv(scenarios_path)
    return df


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


def load_scenario_land(nc_path: str) -> pd.DataFrame:
    df = _load_loc_tech_variable(nc_path, "resource_area", "land_use_km2")
    return df[~df["canton"].isin(FOREIGN_CODES)].copy()


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


def load_scenario_transmission_capacity(nc_path: str) -> pd.DataFrame:
    """Load installed capacity of CH-foreign AC transmission lines."""
    ds = xr.open_dataset(nc_path)
    ch_foreign = get_ch_foreign_transmission_techs(ds)
    cap = ds["energy_cap"].to_pandas()
    ds.close()
    cap = cap.loc[cap.index.isin(ch_foreign)]
    return cap.reset_index().rename(columns={"loc_techs": "loc_tech", "energy_cap": "capacity"})


def get_ch_import_carrier_techs(ds) -> list[str]:
    """loc_tech_carriers_prod Einträge, bei denen CH-Kanton Ursprung und Ausland Ziel ist
    -> carrier_prod hierauf = Import in die Schweiz."""
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
    """Summiert eine Attribut-Spalte über alle Kantone zu einem nationalen Wert."""
    return df[value_col].sum()


def get_ch_fuel_import_techs(ds) -> list[str]:
    """loc_tech_carriers_prod Einträge für alle Brennstoff-Import-Technologien an CH-Standorten
    (z.B. import_syndiesel, import_synmethane, import_hydrogen -- variiert je nach Szenario)."""
    prod_coords = ds.coords["loc_tech_carriers_prod"].values
    result = []
    for c in prod_coords:
        canton, sep, rest = c.partition("::")
        if not sep or canton in FOREIGN_CODES:
            continue
        if rest.startswith("import_") and "ac_transmission" not in rest:
            result.append(c)
    return result


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


SCENARIO_DIR = "../data/raw/scenario_data/"


def scenario_id_from_filename(filename: str) -> str:
    """Extrahiert eine kurze, lesbare Szenario-ID aus dem Dateinamen."""
    base = filename.removesuffix(".nc")
    return base.split(",")[0].replace("barrier_", "")


def extract_all_scenarios(scenario_dir: str = SCENARIO_DIR) -> dict[str, pd.DataFrame]:
    """Läuft über alle Szenario-Dateien und extrahiert alle Attribute.
    Gibt ein dict von DataFrames zurück, je eines pro Attribut, mit scenario_id-Spalte."""
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


def save_all_scenarios(scenario_dir: str = SCENARIO_DIR, out_dir: str = "../data/processed/") -> None:
    os.makedirs(out_dir, exist_ok=True)
    all_data = extract_all_scenarios(scenario_dir)
    for name, df in all_data.items():
        df.to_csv(os.path.join(out_dir, f"scenario_{name}.csv"), index=False)
        print(f"Saved {name}: {len(df)} rows")


def load_canton_area(csv_path: str) -> dict:
    """Lädt Kantonsflächen (km²) aus der Statista-CSV und mappt sie auf Kantonscodes,
    inkl. Merge-Codes (AI_AR, BL_BS, NW_OW) aus Adriens Calliope-Daten."""
    df = pd.read_csv(csv_path, sep=";")
    df.columns = ["canton_name", "area_km2"]
    df["canton_name"] = df["canton_name"].str.strip()
    df["canton_code"] = df["canton_name"].map(CANTON_NAME_TO_CODE)

    area = dict(zip(df["canton_code"], df["area_km2"]))
    for merged_code, parts in CANTON_MERGES.items():
        area[merged_code] = sum(area[p] for p in parts)

    return area


def compute_relative_land(land_df: pd.DataFrame, area_dict: dict) -> pd.DataFrame:
    """Berechnet relative Landnutzung (land_use_km2 / Kantonsfläche) pro Kanton/Technologie,
    passend zur Skala des Choice-Modell-Attributs LAND."""
    land_df = land_df.copy()
    land_df["canton_area_km2"] = land_df["canton"].map(area_dict)
    land_df["relative_land"] = land_df["land_use_km2"] / land_df["canton_area_km2"]
    return land_df


def compute_land_from_capacity(capacity_df: pd.DataFrame, area_dict: dict, density_dict: dict = CAPACITY_DENSITY_GW_PER_KM2) -> pd.DataFrame:
    """Berechnet Landnutzung aus installierter Kapazität via Technologie-spezifischer
    Flächendichte (MW/km²), gemäss Tröndle et al. Methodik (8 MW/km² Wind, 80 MW/km² PV)."""
    df = capacity_df[capacity_df["tech"].isin(density_dict.keys())].copy()
    df["density_mw_per_km2"] = df["tech"].map(density_dict)
    df["land_use_km2"] = df["capacity"] / df["density_mw_per_km2"]
    df["canton_area_km2"] = df["canton"].map(area_dict)
    df["relative_land"] = df["land_use_km2"] / df["canton_area_km2"]
    return df


def load_scenario_net_import(nc_path: str) -> pd.DataFrame:
    """Netto-Electricity-Import (Import - Export) pro CH-Grenzleitung, in GWh."""
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
    """demand_elec plus Stromverbrauch aus Sektorkopplung (SECTOR_COUPLING_ELEC_TECHS) an CH-Standorten.
    Speicher (pumped_hydro, hydrogen_electricity_storage, battery) bewusst nicht enthalten --
    gespeicherter Strom wird später wieder abgegeben und würde doppelt gezählt."""
    con_coords = ds.coords["loc_tech_carriers_con"].values
    sector_coupling = [
        c for c in con_coords
        if c.split("::")[0] not in FOREIGN_CODES
        and c.split("::")[1] in SECTOR_COUPLING_ELEC_TECHS
        and c.endswith("::electricity")
    ]
    return get_ch_demand_elec_techs(ds) + sector_coupling


def load_scenario_demand(nc_path: str) -> pd.DataFrame:
    """Gesamtstromverbrauch pro CH-Kanton und Tech (demand_elec + Sektorkopplung), in GWh."""
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
    """Nationaler Importanteil = Netto-Import / Gesamtverbrauch, geclippt auf [0, 1]
    (das Survey-Attribut kennt keine negativen Werte / Netto-Export)."""
    net_import = aggregate_national(load_scenario_net_import(nc_path), "net_import_gwh")
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    share = net_import / demand
    return max(0.0, min(1.0, share))


def compute_import_share_extended(nc_path: str) -> float:
    """Erweiterter Importanteil = (Strom-Netto-Import + Brennstoff-Import) / Gesamtverbrauch (Strom).
    Eigene Erweiterung über die ursprüngliche Choice-Modell-Definition hinaus (dort nur Strom)."""
    net_import = aggregate_national(load_scenario_net_import(nc_path), "net_import_gwh")
    fuel_import = aggregate_national(load_scenario_fuel_import(nc_path), "fuel_import_gwh")
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    share = (net_import + fuel_import) / demand
    return max(0.0, min(1.0, share))


def compute_ownership_shares(capacity_df: pd.DataFrame, mapping: dict = OWNERSHIP_MAPPING) -> dict:
    """Kapazitätsgewichteter Erwartungswert für ownership_commercial / ownership_community,
    basierend auf einer fixen Technologie-zu-Eigentümer-Zuordnung (Annahme, nicht empirisch).
    Referenzkategorie 'public' hat im Choice-Modell keinen eigenen Beta (impliziter Referenzwert)."""
    df = capacity_df[capacity_df["tech"].isin(mapping.keys())].copy()
    df["ownership_category"] = df["tech"].map(mapping)
    total_capacity = df["capacity"].sum()
    shares = df.groupby("ownership_category")["capacity"].sum() / total_capacity
    return {
        "ownership_commercial": shares.get("commercial", 0.0),
        "ownership_community": shares.get("community", 0.0),
        "ownership_public": shares.get("public", 0.0),  # zur Kontrolle, nicht im Beta verwendet
    }


def compute_technology_mix_shares(capacity_df: pd.DataFrame, mapping: dict = TECH_SOURCE_MAPPING) -> dict:
    """Kapazitätsanteil pro source_*-Kategorie. Der Nenner (total_capacity) umfasst ALLE
    generationsrelevanten Technologien inkl. der PV-Referenzkategorie (PV_REFERENCE_TECHS),
    sonst würde die PV-Kapazität den Nenner künstlich verkleinern und alle Anteile überschätzen."""
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


def fetch_elcom_price(year: int, category: str = "H4", product: str = "standard") -> pd.DataFrame:
    """Holt ElCom-Strompreise (Rp./kWh) pro Gemeinde direkt via LINDAS-SPARQL-Endpoint,
    statt Werte hart zu codieren. category='H4' = Standard-Haushaltskategorie."""
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


def get_elcom_reference_price(year: int = PRICE_REFERENCE_YEAR, category: str = "H4") -> dict:
    """Nationaler Median-Strompreis und Steuer-/Abgaben-Komponente, direkt von ElCom via LINDAS
    (kein Hardcoding). Rückgabe in Rp./kWh."""
    df = fetch_elcom_price(year, category)
    return {
        "total_rp_kwh": df["total"].median(),
        "taxes_levies_rp_kwh": (df["charge"] + df["aidfee"]).median(),
        "netznutzung_rp_kwh": df["grid"].median(),
    }


def load_scenario_system_cost(nc_path: str) -> float:
    """Gesamte CH-Systemkosten (Million EUR/Jahr), summiert über alle CH-Loc-Techs
    (Fremdländer-Loc-Techs ausgeschlossen, analog zu den anderen Attributen)."""
    ds = xr.open_dataset(nc_path)
    cost = ds["cost"]
    classes = list(cost.coords["costs"].values)
    cost = cost.sel(costs="monetary") if "monetary" in classes else cost.sel(costs=classes[0])
    loc_techs = cost.coords["loc_techs_cost"].values
    ch_loc_techs = [lt for lt in loc_techs if lt.split("::")[0] not in FOREIGN_CODES]
    total = cost.sel(loc_techs_cost=ch_loc_techs).sum().item()
    ds.close()
    return total  # Million EUR/Jahr


def fetch_eur_to_chf() -> float:
    """Aktueller EUR/CHF-Wechselkurs, live via Frankfurter API (basiert auf EZB-Referenzkursen),
    statt hartcodiert."""
    response = requests.get("https://api.frankfurter.dev/v1/latest", params={"from": "EUR", "to": "CHF"})
    response.raise_for_status()
    return response.json()["rates"]["CHF"]


def compute_price_change(nc_path: str, year: int = PRICE_REFERENCE_YEAR, category: str = "H4",
                          elcom_ref: dict = None, eur_to_chf: float = None) -> float:
    """Relative Preisänderung ggü. ElCom-Referenzpreis. Bewusst NICHT auf >=0 geclippt
    (im Gegensatz zu Import) -- Price ist ein kontinuierliches, lineares Attribut, milde
    Extrapolation über den Trainingsbereich (0-60% Anstieg) hinaus ist hier vertretbarer
    als z.B. bei Netto-Export."""
    system_cost = load_scenario_system_cost(nc_path)
    demand = aggregate_national(load_scenario_demand(nc_path), "demand_gwh")
    eur_to_chf = eur_to_chf if eur_to_chf is not None else fetch_eur_to_chf()
    cost_per_kwh_chf = (system_cost / demand) * eur_to_chf
    simulated_rp_kwh = cost_per_kwh_chf * 100 * (1 + PRICE_MARGIN)
    ref = elcom_ref if elcom_ref is not None else get_elcom_reference_price(year, category)
    # Netznutzung (Verteilnetz) ist nicht in den Calliope-Systemkosten enthalten -> konstanter Zuschlag
    simulated_rp_kwh += ref["taxes_levies_rp_kwh"] + ref["netznutzung_rp_kwh"]
    return (simulated_rp_kwh - ref["total_rp_kwh"]) / ref["total_rp_kwh"]


def compute_national_relative_land(nc_path: str, area_dict: dict) -> float:
    """Nationaler Durchschnitt der relativen Landnutzung (ungewichtetes Mittel über Kantone).
    Für die spätere regionale Modellanwendung werden die Kanton-Werte separat benötigt
    (compute_land_from_capacity liefert diese granular)."""
    capacity_df = load_scenario_capacity(nc_path)
    land_df = compute_land_from_capacity(capacity_df, area_dict)
    per_canton_land = land_df.groupby("canton")["land_use_km2"].sum()
    per_canton_area = land_df.groupby("canton")["canton_area_km2"].first()
    return (per_canton_land / per_canton_area).mean()


def compute_all_attributes(nc_path: str, area_dict: dict, elcom_ref: dict, eur_to_chf: float) -> dict:
    """Berechnet alle 11 Choice-Modell-Attribute (national) für ein Szenario."""
    capacity_df = load_scenario_capacity(nc_path)
    return {
        # Empirisch verifiziert, kein Platzhalter: die CH-Ausland-AC-Kapazität ist in allen 12
        # Szenarien identisch (13.249 GW je Richtung), Mellot et al. bauen keine Transmission aus.
        "transmission_change": 0.0,
        "relative_land": compute_national_relative_land(nc_path, area_dict),
        # import_share_extended (compute_import_share_extended) bewusst nicht enthalten:
        # Brennstoff- und Strom-GWh sind nicht vergleichbar, Choice-Modell definiert nur Stromimport.
        "import_share": compute_import_share(nc_path),
        **compute_ownership_shares(capacity_df),
        **compute_technology_mix_shares(capacity_df),
        "price_change": compute_price_change(nc_path, elcom_ref=elcom_ref, eur_to_chf=eur_to_chf),
    }


def compute_all_scenarios(scenario_dir: str = SCENARIO_DIR, area_csv_path: str = None) -> pd.DataFrame:
    """Läuft alle fertigen Attribut-Funktionen über alle Szenario-Dateien; ElCom-Referenzpreis und
    EUR/CHF-Kurs werden einmal geholt (nicht pro Szenario) und wiederverwendet."""
    area_dict = load_canton_area(area_csv_path)
    elcom_ref = get_elcom_reference_price()
    eur_to_chf = fetch_eur_to_chf()

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


def get_swissgrid_report_url(year: int) -> str:
    """Findet dynamisch die Swissgrid-Download-URL für ein gegebenes Jahr (statt die
    Jahr->URL-Zuordnung hart zu codieren -- die URLs enthalten eine Asset-ID, die sich
    nicht aus dem Jahr ableiten lässt).
    HINWEIS: dieses File enthält nur nationale Produktions-/Verbrauchsstatistiken, keine
    Grenzkapazitäten -- für Transmission daher nicht direkt nutzbar (siehe Notizen)."""
    response = requests.get(SWISSGRID_LISTING_URL)
    response.raise_for_status()
    match = re.search(
        rf'(https://www\.swissgrid\.ch/dam/jcr:[a-f0-9-]+/EnergieUebersichtCH-{year}\.xlsx)',
        response.text,
    )
    if not match:
        raise ValueError(f"Keine Swissgrid-Report-URL für {year} gefunden.")
    return match.group(1)


def download_swissgrid_report(year: int = TRANSMISSION_REFERENCE_YEAR, out_dir: str = "../data/raw/") -> str:
    """Lädt den Swissgrid-Jahresbericht für ein gegebenes Jahr herunter und speichert ihn lokal."""
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