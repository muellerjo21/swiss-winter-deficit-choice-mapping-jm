"""Constants of the first, 6-attribute approach (legacy/choice_model.py, 02_single_scenario.ipynb).
Not maintained. Requires src/ on sys.path (for config)."""
from config import PROJECT_ROOT, RAW_DIR

# Old model from the paper, per country (DNK/DEU/PRT/POL/NOT_SAMPLED), 6 attributes
DATA_PATH = RAW_DIR / "choice-model-inference.nc"
# Manually compiled values from Mellot et al. (same users as DATA_PATH)
SCENARIOS_PATH = PROJECT_ROOT / "legacy" / "data" / "manual" / "scenarios.csv"

# Attribute maxima from Tröndle et al.'s paper and the old technology keys. The current pipeline
# reads the scaling from the model file (load_attribute_scale) and computes relative land use per
# canton (CANTON_AREA_CSV_PATH).
ATTRIBUTE_MAX_VALUES = {
    "LAND": 0.08,
    "PRICES": 0.60,
    "SHARE_IMPORTS": 0.90,
    "TRANSMISSION": 0.75,
}

TECHNOLOGY_KEYS = ["TECHNOLOGY:Open-field PV", "TECHNOLOGY:Wind"]
