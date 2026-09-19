from pathlib import Path

# Ordner, in dem diese config.py selbst liegt (src/)
SRC_DIR = Path(__file__).resolve().parent

# Projekt-Root ist eine Ebene über src/
PROJECT_ROOT = SRC_DIR.parent

DATA_PATH = PROJECT_ROOT / "data" / "raw" / "choice-model-inference.nc"
SCENARIOS_PATH = PROJECT_ROOT / "data" / "manual" / "scenarios.csv"