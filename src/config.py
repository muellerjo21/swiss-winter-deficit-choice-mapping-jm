"""Constants shared by the scripts, all read from the workflow configuration without defaults of their own: a missing
key stops with an error that names it. Inside the workflow this is the configuration of the run including its
--config overrides (the Snakefile passes it in the environment variable SWISS_WINTER_DEFICIT_CONFIG); interactive use
reads config/default.yaml. Only structural code mappings (column names of the attribute tables) are defined here."""
import json
import os
from pathlib import Path

import yaml

# Directory containing config.py (src/) and the project root one level above
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent
CONFIG_ENVIRONMENT_VARIABLE = "SWISS_WINTER_DEFICIT_CONFIG"


def _load_config() -> dict:
    text = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE)
    if text:
        return json.loads(text)
    return yaml.safe_load((PROJECT_ROOT / "config" / "default.yaml").read_text())


_WORKFLOW_CONFIG = _load_config()


def setting(*keys):
    """Configuration value at the key path keys, e.g. setting("attributes", "ownership"); KeyError naming the path
    if it is missing."""
    value = _WORKFLOW_CONFIG
    for i, key in enumerate(keys):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(f"config key {'.'.join(str(k) for k in keys[:i + 1])} is missing (config/default.yaml)")
        value = value[key]
    return value


# For every choice model (data.choice_models), the mapping of the Swiss coefficient groups (DE-CH, FR-CH) to the
# group/country of its file (load_data.model_partworths)
_CHOICE_MODELS = setting("data", "choice_models")
CHOICE_MODEL_COUNTRIES = {str((PROJECT_ROOT / m["file"]).resolve()): m["coefficients"] for m in _CHOICE_MODELS.values()}

# Regions of the Calliope model (regions in config/default.yaml): canton codes by German name and by BFS number,
# merged locations, language region per location, foreign locations
_CANTONS = setting("regions", "cantons")
CANTON_NAME_TO_CODE = {canton["name"]: code for code, canton in _CANTONS.items()}
CANTON_NUMBER_TO_CODE = {canton["number"]: code for code, canton in _CANTONS.items()}
CANTON_MERGES = setting("regions", "merged_cantons")
CANTON_LANGUAGE = setting("regions", "language")
FOREIGN_CODES = set(setting("calliope", "foreign_locations"))


def region_of_canton(canton: str) -> str:
    """Calliope location of a canton (merged cantons, e.g. AI -> AI_AR)."""
    return next((merged for merged, parts in CANTON_MERGES.items() if canton in parts), canton)


# Weights of the language regions (regions.language_shares, normalised) and the language groups in this order
_LANGUAGE_SHARES = setting("regions", "language_shares")
LANGUAGE_REGION_WEIGHTS = {group: share / sum(_LANGUAGE_SHARES.values()) for group, share in _LANGUAGE_SHARES.items()}
LANGUAGE_GROUPS = list(LANGUAGE_REGION_WEIGHTS)
GROUP_TAGS = ["national", *(group.replace("-", "_") for group in LANGUAGE_GROUPS)]  # panel order of the figures

# Mapping of the Calliope results to the choice-model attributes (attributes in config/default.yaml)
CAPACITY_DENSITY_GW_PER_KM2 = setting("attributes", "capacity_density_gw_per_km2")
PV_REFERENCE_TECHS = setting("attributes", "pv_reference_techs")
OWNERSHIP_MAPPING = setting("attributes", "ownership")
TECH_SOURCE_MAPPING = setting("attributes", "source")
OWNERSHIP_EXCLUDED_TECHS = setting("attributes", "ownership_excluded")
SOURCE_EXCLUDED_TECHS = setting("attributes", "source_excluded")
TRANSMISSION_CHANGE = setting("attributes", "transmission_change")

# Conventions of the result files (calliope in config/default.yaml) and the end-use technologies per carrier
# (price.end_use_techs, taxes and levies per carrier of cost_scope energy)
COST_CLASS = setting("calliope", "cost_class")
ELECTRICITY_CARRIER = setting("calliope", "electricity_carrier")
DEMAND_ELECTRICITY_TECH = setting("calliope", "demand_electricity_tech")
DEMAND_TECH_PREFIX = setting("calliope", "demand_tech_prefix")
TRANSMISSION_TECH = setting("calliope", "transmission_tech")
HEAT_DEMAND_TECHS = tuple(setting("calliope", "heat_demand_techs"))
TRANSPORT_MARKER = setting("calliope", "transport_marker")
SECTOR_COUPLING_ELEC_TECHS = setting("calliope", "sector_coupling_electricity_techs")
END_USE_TECHS = setting("price", "end_use_techs")

# Download endpoints and the ElCom tariff product of the fetch rules
SOURCES = setting("sources")
ELCOM_PRODUCT = setting("price", "elcom_product")

# Column in scenario_attributes_summary (compute_all_attributes) -> attribute coordinate in the
# choice model (data.choice_models). Structural: names of the code, not a modelling choice.
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

# Unit of the raw scenario attribute z_k per model attribute; beta_real_k = beta_k / sigma_k is the
# utility per one unit of z_k (e.g. per 1.0 = 100 percentage points of a share). cost and import depend on the price
# and import definition of the run: attribute_units.
ATTRIBUTE_UNITS = {
    "source_wind": "share of generation capacity excl. hydro (GW/GW, 0..1)",
    "source_coal": "share of generation capacity excl. hydro (GW/GW, 0..1)",
    "source_gas": "share of generation capacity excl. hydro (GW/GW, 0..1)",
    "source_nuclear": "share of generation capacity excl. hydro (GW/GW, 0..1)",
    "source_biomass": "share of generation capacity excl. hydro (GW/GW, 0..1)",
    "transmission": "relative change of the transmission capacity (-)",
    "land": "land use of wind and open-field/alpine PV / area (km²/km²)",
    "ownership_commercial": "share of generation capacity incl. hydro (GW/GW, 0..1)",
    "ownership_community": "share of generation capacity incl. hydro (GW/GW, 0..1)",
}

_IMPORTS = {"electricity": "net electricity import",
            "electricity_fuels": "net electricity import + imports of natural gas, hydrogen and synthetic methane",
            "electricity_fuels_diesel": "net electricity import + imports of natural gas, hydrogen, synthetic methane and "
                                        "synthetic diesel"}
_DENOMINATORS = {"electricity": "electricity consumption", "final_energy": "final energy (electricity, heat, transport)"}


def attribute_units(cost_scope: str, import_definition: str, import_denominator: str) -> dict:
    """ATTRIBUTE_UNITS with the units of cost and import for the price definition (price.cost_scope) and the import
    definition (imports.definition, imports.denominator; the definition electricity is always over the electricity
    consumption, load_data.compute_import_share)."""
    cost = ("relative change of the energy price per kWh of final energy vs. p_ref (-, 0.1 = +10 %)" if cost_scope == "energy"
            else "relative change of the electricity price vs. the ElCom reference (-, 0.1 = +10 %)")
    denominator = "electricity" if import_definition == "electricity" else import_denominator
    imports = f"{_IMPORTS[import_definition]} / {_DENOMINATORS[denominator]} (GWh/GWh, 0..1)"
    return {**ATTRIBUTE_UNITS, "cost": cost, "import": imports}


# Official cost change of the scenarios relative to EP2050+ (mellot_cost_change_pct: Mellot et al. 2024, Table 3);
# NaN for the scenario that is not in Table 3
MELLOT_COST_CHANGE_PCT = {scenario: float(value) for scenario, value in setting("mellot_cost_change_pct").items()}

# Readable scenario names for figures and texts (figures.display_names)
SCENARIO_DISPLAY_NAMES = setting("figures", "display_names")
