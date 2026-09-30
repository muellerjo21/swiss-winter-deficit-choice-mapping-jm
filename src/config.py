from pathlib import Path

# Ordner, in dem diese config.py selbst liegt (src/)
SRC_DIR = Path(__file__).resolve().parent

# Projekt-Root ist eine Ebene über src/
PROJECT_ROOT = SRC_DIR.parent

# Neues Choice-Modell (Jan 2026), pro Sprachregion (DE-CH/FR-CH/...), 11 Attribute
CHOICE_MODEL_PATH = PROJECT_ROOT / "data" / "raw" / "choice-model-jan-2026.nc"
# Altes Modell aus Tims Paper, pro Land (DNK/DEU/PRT/POL/NOT_SAMPLED), 6 Attribute
# -- nur noch von choice_model.py / 02_single_scenario.ipynb genutzt
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "choice-model-inference.nc"
SCENARIOS_PATH = PROJECT_ROOT / "data" / "manual" / "scenarios.csv"

ATTRIBUTE_MAX_VALUES = {
    "LAND": 0.08,
    "PRICES": 0.60,
    "SHARE_IMPORTS": 0.90,
    "TRANSMISSION": 0.75,
}

SWISS_LAND_AREA_KM2 = 41_285
TECHNOLOGY_KEYS = ["TECHNOLOGY:Open-field PV", "TECHNOLOGY:Wind"]

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
    "TI": None,  # Italienisch, nicht im Choice-Modell abgedeckt
}

FOREIGN_CODES = {"AUT", "DEU", "FRA", "ITA"}

CANTON_NAME_TO_CODE = {
    "Zürich": "ZH", "Bern": "BE", "Luzern": "LU", "Uri": "UR", "Schwyz": "SZ",
    "Obwalden": "OW", "Nidwalden": "NW", "Glarus": "GL", "Zug": "ZG", "Freiburg": "FR",
    "Solothurn": "SO", "Basel-Stadt": "BS", "Basel-Landschaft": "BL", "Schaffhausen": "SH",
    "Appenzell Ausserrhoden": "AR", "Appenzell Innerrhoden": "AI", "St. Gallen": "SG",
    "Graubünden": "GR", "Aargau": "AG", "Thurgau": "TG", "Tessin": "TI", "Waadt": "VD",
    "Wallis": "VS", "Neuenburg": "NE", "Genf": "GE", "Jura": "JU",
}

CANTON_MERGES = {
    "AI_AR": ["AI", "AR"],
    "BL_BS": ["BL", "BS"],
    "NW_OW": ["NW", "OW"],
}

# Flächendichte pro Technologie (GW/km²), gemäss Tröndle et al. Methodik
# (8 MW/km² Wind, 80 MW/km² PV -- gilt für alle PV- bzw. Wind-Subtypen gleich).
# roof_mounted_pv bewusst ausgeschlossen: Dachflächen sind keine zusätzlich beanspruchte Fläche.
CAPACITY_DENSITY_GW_PER_KM2 = {
    "wind_onshore_monopoly": 0.008,
    "wind_onshore_competing": 0.008,
    "open_field_pv": 0.08,
    "alpine_pv_subsidised": 0.08,
    "alpine_pv_not_subsidised": 0.08,
}

# Annahme (nicht empirisch): Technologie -> Eigentümerkategorie für compute_ownership_shares.
# "public" ist die implizite Referenzkategorie im Choice-Modell.
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

# Technologie -> source_*-Kategorie im Choice-Modell.
# roof_mounted_pv, open_field_pv, alpine_pv_* -> implizite Referenzkategorie (Solar/PV),
# kein eigener Beta, aber Teil des Kapazitäts-Nenners in compute_technology_mix_shares.
# source_coal, source_nuclear: keine entsprechende CH-Technologie vorhanden -> Anteil immer 0.
# hydro_reservoir, hydro_run_of_river, pumped_hydro: bewusst ausgeschlossen -- das Choice-Modell
# kennt keine Hydro-Kategorie, und Mellot et al. frieren Hydro-Kapazitäten über alle Szenarien
# ein ("we freeze the installed capacities to today's levels"), tragen also ohnehin nicht zur
# Szenario-Variation bei.
TECH_SOURCE_MAPPING = {
    "wind_onshore_monopoly": "source_wind",
    "wind_onshore_competing": "source_wind",
    "ccgt": "source_gas",
    "ccgt_natgas": "source_gas",
    "chp_methane": "source_gas",
    "chp_biofuel": "source_biomass",
    "chp_waste": "source_biomass",
}

# Zusätzliche Technologien, die zwar keine eigene source_*-Kategorie haben (PV = impliziter
# Referenzwert), aber trotzdem Teil des Kapazitäts-Nenners sein müssen (compute_technology_mix_shares)
# bzw. der Landnutzungsberechnung (compute_land_from_capacity via CAPACITY_DENSITY_GW_PER_KM2).
# Techs mit Strom als Input (Sektorkopplung), die zusätzlich zu demand_elec als Stromverbrauch
# zählen (Nenner für import_share und price_change). Speicher (pumped_hydro,
# hydrogen_electricity_storage, battery) bewusst nicht enthalten -> Doppelzählung.
SECTOR_COUPLING_ELEC_TECHS = [
    "light_transport_ev", "heavy_transport_ev", "hp", "electrode_boiler",
    "electrolysis", "dac", "daccs_local",
]

PV_REFERENCE_TECHS = ["roof_mounted_pv", "open_field_pv", "alpine_pv_subsidised", "alpine_pv_not_subsidised"]

PRICE_MARGIN = 0.10          # Tröndle's assumed 10% revenue margin

PRICE_REFERENCE_YEAR = 2025  # Baseline-Jahr des Choice-Experiments ("...compared with 2022's levels")
TRANSMISSION_REFERENCE_YEAR = PRICE_REFERENCE_YEAR  # gleiche "heute"-Referenzjahr-Logik wie Price

# Spalte in scenario_attributes_summary (compute_all_attributes) -> attribute-Koordinate im
# Choice-Modell (CHOICE_MODEL_PATH).
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

# Quelle: Bundesamt für Statistik (BFS), "Sprachliche Praktiken in der
# Schweiz", Strukturerhebung 2023. Hauptsprachen der staendigen
# Wohnbevoelkerung: Deutsch 61%, Franzoesisch 23% (Mehrfachnennungen
# moeglich). Hier normalisiert auf DE-CH/FR-CH allein (analog
# CANTON_LANGUAGE, TI/Raetoromanisch ausgeklammert):
# https://dam-api.bfs.admin.ch/hub/api/dam/assets/34788128/master
LANGUAGE_REGION_WEIGHTS = {
    "DE-CH": 61 / (61 + 23),  # 0.726
    "FR-CH": 23 / (61 + 23),  # 0.274
}

# Offizielle Kostenänderung der Szenarien relativ zu EP2050+ ("Swiss cost change [%]"), aus
# Mellot et al. (2024), Energy Conversion and Management 309, 118426, Table 3.
# "baseline" (EP2050+ mit 5-TWh-Winter-Constraint) ist nicht in Table 3 enthalten -> NaN.
MELLOT_COST_CHANGE_PCT = {
    "policy_mix": -17.0,                                # MIX
    "policy_sccgt_daccs": -16.3,                        # S/CCGT (Fossil) + DACCS
    "policy_remix": -8.8,                               # RE MIX
    "policy_sccgt_plus_h2": -3.6,                       # S/CCGT (Ren. Methane) +H2
    "policy_sccgt_no_h2": -3.6,                         # S/CCGT (Ren. Methane)
    "policy_alpine_pv": -0.8,                           # Alpine PV
    "baseline_no_self_sufficiency_result_4H": 0.0,      # EP2050+ (Referenz)
    "policy_wind_x2": 18.0,                             # Wind
    "policy_h2_imports_only": 19.2,                     # H2Imports
    "policy_chp": 22.2,                                 # CHP
    "policy_roof_pv": 33.7,                             # Roof PV++
    "baseline": float("nan"),                           # nicht in Table 3
}

# Lesbare Szenario-Namen für Abbildungen, gemäss Mellot et al. (2024), Table 3.
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
