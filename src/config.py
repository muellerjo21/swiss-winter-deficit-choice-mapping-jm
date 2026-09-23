from pathlib import Path

# Ordner, in dem diese config.py selbst liegt (src/)
SRC_DIR = Path(__file__).resolve().parent

# Projekt-Root ist eine Ebene über src/
PROJECT_ROOT = SRC_DIR.parent

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
    "ZH": "DE-CH", "BE": "DE-CH", "LU": "DE-CH", "UR": "DE-CH", "SZ": "DE-CH",
    "OW": "DE-CH", "NW": "DE-CH", "GL": "DE-CH", "ZG": "DE-CH", "SO": "DE-CH",
    "BS": "DE-CH", "BL": "DE-CH", "SH": "DE-CH", "AR": "DE-CH", "AI": "DE-CH",
    "SG": "DE-CH", "GR": "DE-CH", "AG": "DE-CH", "TG": "DE-CH",
    "FR": "FR-CH", "VD": "FR-CH", "VS": "FR-CH", "NE": "FR-CH",
    "GE": "FR-CH", "JU": "FR-CH",
    "TI": None,  # Italienisch, nicht im Choice-Modell abgedeckt
}