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