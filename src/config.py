from pathlib import Path

# Directory containing config.py (src/)
SRC_DIR = Path(__file__).resolve().parent

# Project root is one level above src/
PROJECT_ROOT = SRC_DIR.parent

# Choice model (Jan 2026), per language region
CHOICE_MODEL_PATH = PROJECT_ROOT / "data" / "raw" / "choice-model-jan-2026.nc"

# LEGACY: old model from the paper, per country (DNK/DEU/PRT/POL/NOT_SAMPLED), 6 attributes
# -- only used by choice_model.py / 02_single_scenario.ipynb
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "choice-model-inference.nc"
# LEGACY: manually compiled values from Mellot et al. (same users as DATA_PATH)
SCENARIOS_PATH = PROJECT_ROOT / "data" / "manual" / "scenarios.csv"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Calliope results of Mellot et al., one .nc per scenario
SCENARIO_DIR = RAW_DIR / "scenario_data"

# Canton areas (km², Statista/BFS), for relative land use
CANTON_AREA_CSV_PATH = RAW_DIR / "flache_der_schweiz_nach_kantonen_in_quadratkilometern.csv"

# LEGACY (old model, only used by choice_model.py / 02_single_scenario.ipynb): attribute maxima
# from Tröndle et al.'s paper, the national land area and the old technology keys. The current
# pipeline reads the scaling from the model file (load_attribute_scale) and computes relative land
# use per canton (CANTON_AREA_CSV_PATH).
ATTRIBUTE_MAX_VALUES = {
    "LAND": 0.08,
    "PRICES": 0.60,
    "SHARE_IMPORTS": 0.90,
    "TRANSMISSION": 0.75,
}

SWISS_LAND_AREA_KM2 = 41_285
TECHNOLOGY_KEYS = ["TECHNOLOGY:Open-field PV", "TECHNOLOGY:Wind"]

# Canton names (German) -> BFS abbreviations

CANTON_NAME_TO_CODE = {
    "Zürich": "ZH", 
    "Bern": "BE", 
    "Luzern": "LU", 
    "Uri": "UR", 
    "Schwyz": "SZ",
    "Obwalden": "OW", 
    "Nidwalden": "NW",
    "Glarus": "GL", 
    "Zug": "ZG", 
    "Freiburg": "FR",
    "Solothurn": "SO", 
    "Basel-Stadt": "BS", 
    "Basel-Landschaft": "BL", 
    "Schaffhausen": "SH",
    "Appenzell Ausserrhoden": "AR", 
    "Appenzell Innerrhoden": "AI", 
    "St. Gallen": "SG",
    "Graubünden": "GR", 
    "Aargau": "AG", 
    "Thurgau": "TG", 
    "Tessin": "TI", 
    "Waadt": "VD",
    "Wallis": "VS", 
    "Neuenburg": "NE", 
    "Genf": "GE", 
    "Jura": "JU",
}

CANTON_MERGES = {
    "AI_AR": ["AI", "AR"],
    "BL_BS": ["BL", "BS"],
    "NW_OW": ["NW", "OW"],
}

CANTON_LANGUAGE = {
    "ZH": "DE-CH",
    "BE": "DE-CH",
    "LU": "DE-CH",
    "UR": "DE-CH",
    "SZ": "DE-CH",
    "GL": "DE-CH",
    "ZG": "DE-CH",
    "SO": "DE-CH",
    "SH": "DE-CH",
    "SG": "DE-CH",
    "GR": "DE-CH",
    "AG": "DE-CH",
    "TG": "DE-CH",
    "FR": "FR-CH",
    "VD": "FR-CH",
    "VS": "FR-CH",
    "NE": "FR-CH",
    "GE": "FR-CH",
    "JU": "FR-CH",
    "AI_AR": "DE-CH",
    "BL_BS": "DE-CH",
    "NW_OW": "DE-CH",
    "TI": None,  # Italian-speaking, not covered by the choice model
}

FOREIGN_CODES = {"AUT", "DEU", "FRA", "ITA"}


# Capacity density per technology (GW/km²), following Tröndle et al.'s methodology
# (8 MW/km² wind, 80 MW/km² PV -- applies equally to all PV and wind subtypes).
# roof_mounted_pv deliberately excluded: rooftops do not occupy additional land.
CAPACITY_DENSITY_GW_PER_KM2 = {
    "wind_onshore_monopoly": 0.008,
    "wind_onshore_competing": 0.008,
    "open_field_pv": 0.08,
    "alpine_pv_subsidised": 0.08,
    "alpine_pv_not_subsidised": 0.08,
}

# Assumption (not empirical): technology -> ownership category for compute_ownership_shares.
# "public" is the implicit reference category in the choice model.
OWNERSHIP_MAPPING = {
    "roof_mounted_pv": "commercial",
    "open_field_pv": "commercial",
    "alpine_pv_subsidised": "commercial",
    "alpine_pv_not_subsidised": "commercial",
    "wind_onshore_monopoly": "community",
    "wind_onshore_competing": "community",
    "ccgt": "commercial",
    "ccgt_natgas": "commercial",
    "chp_methane": "commercial",
    "chp_waste": "commercial",
    "chp_biofuel": "commercial",
    "hydro_run_of_river": "public",
    "hydro_reservoir": "public",
    "pumped_hydro": "public",
    "nuclear": "public",
}

# Technology -> source_* category in the choice model.
# roof_mounted_pv, open_field_pv, alpine_pv_* -> implicit reference category (solar/PV),
# no beta of their own, but part of the capacity denominator in compute_technology_mix_shares.
# source_coal, source_nuclear: no corresponding Swiss technology -> share always 0.
# hydro_reservoir, hydro_run_of_river, pumped_hydro: deliberately excluded -- the choice model
# has no hydro category, and Mellot et al. freeze hydro capacities across all scenarios
# ("we freeze the installed capacities to today's levels"), so they do not contribute to
# scenario variation anyway.
TECH_SOURCE_MAPPING = {
    "wind_onshore_monopoly": "source_wind",
    "wind_onshore_competing": "source_wind",
    "ccgt": "source_gas",
    "ccgt_natgas": "source_gas",
    "chp_methane": "source_gas",
    "chp_biofuel": "source_biomass",
    "chp_waste": "source_biomass",
}

# Techs with electricity as input (sector coupling) that count as electricity consumption in
# addition to demand_elec (denominator for import_share and price_change). Storage (pumped_hydro,
# hydrogen_electricity_storage, battery) deliberately excluded -> would double-count.
SECTOR_COUPLING_ELEC_TECHS = [
    "light_transport_ev", "heavy_transport_ev", "hp", "electrode_boiler",
    "electrolysis", "dac", "daccs_local",
]

# Technologies without a source_* category of their own (PV = implicit reference), which must
# still be part of the capacity denominator (compute_technology_mix_shares) and of the land-use
# calculation (compute_land_from_capacity via CAPACITY_DENSITY_GW_PER_KM2).
PV_REFERENCE_TECHS = ["roof_mounted_pv", "open_field_pv", "alpine_pv_subsidised", "alpine_pv_not_subsidised"]

PRICE_MARGIN = 0.10          # Tröndle's assumed 10% revenue margin

# Already reproducible, no pinning needed: ElCom tariffs change only once per year and the year
# is fixed -> get_elcom_reference_price() returns the same reference price on every run.
PRICE_REFERENCE_YEAR = 2025  # Baseline year of the choice experiment ("...compared with 2022's levels")
# ECB EUR/CHF reference rate for the price conversion, fixed instead of /latest (Snakemake
# reproducibility). Date of the rate (0.9461) used to compute the validated values in
# scenario_attributes_summary.csv (back-calculated from the stored price_change, the only
# match in the period).
PRICE_REFERENCE_DATE = "2026-09-29"
TRANSMISSION_REFERENCE_YEAR = PRICE_REFERENCE_YEAR  # same "today" reference-year logic as price

# Column in scenario_attributes_summary (compute_all_attributes) -> attribute coordinate in the
# choice model (CHOICE_MODEL_PATH).
ATTRIBUTE_COLUMN_TO_MODEL_TERM = {
    "source_wind": "source_wind",
    "source_coal": "source_coal",
    "source_gas": "source_gas",
    "source_nuclear": "source_nuclear",
    "source_biomass": "source_biomass",
    "price_change": "cost",
    "import_share": "import",
    "transmission_change": "transmission",
    "relative_land": "land",
    "ownership_commercial": "ownership_commercial",
    "ownership_community": "ownership_community",
}

# Source: Swiss Federal Statistical Office (BFS), "Sprachliche Praktiken in der Schweiz",
# structural survey 2023. Main languages of the permanent resident population: German 61%,
# French 23% (multiple answers possible). Normalised here to DE-CH/FR-CH only (analogous to
# CANTON_LANGUAGE, Italian/Romansh excluded):
# https://dam-api.bfs.admin.ch/hub/api/dam/assets/34788128/master
LANGUAGE_REGION_WEIGHTS = {
    "DE-CH": 61 / (61 + 23),  # 0.726
    "FR-CH": 23 / (61 + 23),  # 0.274
}

# Official cost change of the scenarios relative to EP2050+ ("Swiss cost change [%]"), from
# Mellot et al. (2024), Energy Conversion and Management 309, 118426, Table 3.
# "baseline" (EP2050+ with 5 TWh winter constraint) is not in Table 3 -> NaN.
MELLOT_COST_CHANGE_PCT = {
    "policy_mix": -17.0,                                # MIX
    "policy_sccgt_daccs": -16.3,                        # S/CCGT (Fossil) + DACCS
    "policy_remix": -8.8,                               # RE MIX
    "policy_sccgt_plus_h2": -3.6,                       # S/CCGT (Ren. Methane) +H2
    "policy_sccgt_no_h2": -3.6,                         # S/CCGT (Ren. Methane)
    "policy_alpine_pv": -0.8,                           # Alpine PV
    "baseline_no_self_sufficiency_result_4H": 0.0,      # EP2050+ (reference)
    "policy_wind_x2": 18.0,                             # Wind
    "policy_h2_imports_only": 19.2,                     # H2Imports
    "policy_chp": 22.2,                                 # CHP
    "policy_roof_pv": 33.7,                             # Roof PV++
    "baseline": float("nan"),                           # not in Table 3
}

# Readable scenario names for figures, following Mellot et al. (2024), Table 3.
SCENARIO_DISPLAY_NAMES = {
    "policy_mix": "MIX",
    "policy_sccgt_daccs": "S/CCGT (Fossil) + DACCS",
    "policy_remix": "RE MIX",
    "policy_sccgt_plus_h2": "S/CCGT (Ren. Methane) + H2",
    "policy_sccgt_no_h2": "S/CCGT (Ren. Methane)",
    "policy_alpine_pv": "Alpine PV",
    "baseline_no_self_sufficiency_result_4H": "EP2050+",
    "policy_wind_x2": "Wind",
    "policy_h2_imports_only": "H2 Imports",
    "policy_chp": "CHP",
    "policy_roof_pv": "Roof PV++",
    "baseline": "EP2050+ (5 TWh winter cap)",
}
