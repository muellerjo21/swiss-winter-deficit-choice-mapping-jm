import json
import os
import re
import sys

from snakemake.utils import min_version
from pathlib import Path

configfile: "config/default.yaml"
min_version("9.6")

include: "rules/common.smk"

config.update(numbers_from_text(dict(config)))
# The scripts read the configuration of this run, including --config overrides, through src/config.py
os.environ.update({"SWISS_WINTER_DEFICIT_CONFIG": json.dumps(config)})

WEATHER_YEAR = config["weather_year"]  # weather year of the main analysis (2016 = main result)
WEATHER_YEARS = config["sensitivity"]["weather_years"]  # weather years compared (rule weather_year_rankings)
SCENARIOS = scenario_files(WEATHER_YEAR)  # scenario ID -> .nc file name (main analysis)
SCENARIO_DIR = scenario_dir(WEATHER_YEAR)
SCENARIOS_BY_YEAR = {y: SCENARIOS if y == WEATHER_YEAR else scenario_files(y) for y in WEATHER_YEARS}
COMMON_SCENARIOS = [s for s in config["scenarios"] if all(s in SCENARIOS_BY_YEAR[y] for y in WEATHER_YEARS)]
FIGURES = [  # national aggregate (appendix), created by src/make_graphics.make_all
    "fig1_rank_choice_vs_cost_national", "fig2_utility_forest_national", "fig3_utility_contributions_national",
    "fig4_rank_de_vs_fr_national", "fig5_cost_vs_preference_national", "figA1_utility_contributions_absolute_national",
]
FIGURE_FORMATS = ["png", "pdf", "svg"]
PNG_PDF = ["png", "pdf"]  # figures without SVG (pairwise matrix, maps, fig11) and the fig6 test reference
TEST_REPORT = "build/test-report.html"  # log of rule test, read by the pipeline map
FIGURE_PATH = "build/figures/{fmt}/{figure}.{fmt}"  # one subfolder per format
REFERENCE_YEAR = config["price"]["reference_year"]
COST_SCALE = config["price"]["cost_scale_factor"]  # factor on the Calliope system cost (1.0 = main analysis)
COST_SCOPE = config["price"]["cost_scope"]  # costs in the price formula: energy (main analysis) | total | electricity | electricity_fuel
COST_GROUPS = config["price"]["cost_groups"]
POWER_FUEL = dict(plants=config["price"]["fuel_power_techs"], fuels=config["price"]["fuel_carriers"],
                  chp_allocation=config["price"]["chp_fuel_allocation"])  # cost_scope electricity_fuel
# cost_scope energy: p_ref, tau + g (entry price.energy_surcharge of price.energy_surcharges: a number, a dict carrier ->
# rate, or null = ElCom electricity values) and VAT
# Choice model: entry data.choice_model of data.choice_models (file, Swiss coefficient groups, mobile shift)
CHOICE_MODEL = config["data"]["choice_models"][config["data"]["choice_model"]]
if float(config["utility"]["mobile_share"]) != 0 and not CHOICE_MODEL["mobile_partworths"]:
    raise ValueError(f"utility.mobile_share needs a choice model with mobile_partworths, not {config['data']['choice_model']}")
ENERGY_SURCHARGE = config["price"]["energy_surcharges"][config["price"]["energy_surcharge"]]
ENERGY_REFERENCE = dict(reference=config["price"]["energy_reference_ct_per_kwh"],
                        surcharge=ENERGY_SURCHARGE.get("ct_per_kwh_by_carrier", ENERGY_SURCHARGE.get("ct_per_kwh")),
                        vat=config["price"]["energy_vat"])
MARGIN = config["price"]["margin"]  # revenue margin mu of the price formula
IMPORTS = {k: config["imports"][k] for k in ("definition", "denominator", "fuel_techs", "diesel_techs")}  # import attribute
# Settings that the scripts read through src/config.py instead of params (conventions of the result files, regions,
# attribute mappings, Mellot Table 3, end-use technologies, choice models, display names). As a param of every
# analysis rule, a change of them re-runs the rules.
MODEL_SETTINGS = {key: config[key] for key in ("calliope", "regions", "attributes", "mellot_cost_change_pct")}
MODEL_SETTINGS.update(end_use_techs=config["price"]["end_use_techs"], choice_models=config["data"]["choice_models"],
                      display_names=config["figures"]["display_names"])
SENSITIVITY = config["sensitivity"]
FIGURE_SENSITIVITY = "fig6_p_rank1_vs_reference_price_national"  # created by src/make_graphics.fig_reference_price_sensitivity
SENSITIVITY_YEARS = sorted(set(SENSITIVITY["base_years"]) | {REFERENCE_YEAR})
REGIONAL = config["spatial"]["regional"]
# Ticino (spatial.regional.ticino): coefficients TI is computed with, or excluded
TICINO_COEFFICIENTS = {"exclude": None, "de": "DE-CH", "fr": "FR-CH", "mixed": "mixed"}
if REGIONAL["ticino"] not in TICINO_COEFFICIENTS:
    raise ValueError(f"spatial.regional.ticino must be one of {list(TICINO_COEFFICIENTS)}, got {REGIONAL['ticino']!r}")
TICINO = TICINO_COEFFICIENTS[REGIONAL["ticino"]]
EXCLUDE = ["TI"] if TICINO is None else []  # regions left out of the regional analysis
COEFFICIENT_OVERRIDES = {} if TICINO is None else {"TI": TICINO}  # region -> coefficients instead of its language
FIGURES_REGIONAL = [  # created by src/make_graphics.make_all_regional
    "fig1_rank_choice_vs_cost_regional", "fig2_utility_forest_regional", "fig3_utility_contributions_regional",
    "fig4_rank_de_vs_fr_regional", "fig5_cost_vs_preference_regional", "figA1_utility_contributions_absolute_regional",
    "fig6_p_rank1_vs_reference_price_shift_regional", "fig7_rank1_by_region_regional",
    "fig8_rank1_population_share_regional",
]
FIGURES_CONFIG = config["figures"]
PAIRWISE = config["pairwise"]
MAPS = config["maps"]
MAP_PAIRS = [f"{a}_vs_{b}" for a, b in PAIRWISE["map_pairs"]]
FIGURE_PAIRWISE = "fig9_pairwise_choice_probability_regional"
MAP_RANGES = [MAPS["color_range"], MAPS["color_range_variant"]]
MAP_RANGE_TAGS = ["", "_range{}-{}".format(*MAPS["color_range_variant"])]
FIGURES_MAPS_BY_PAIR = [[f"fig10_choice_map_{pair}{tag}_regional" for tag in MAP_RANGE_TAGS] for pair in MAP_PAIRS]
FIGURES_MAPS = [name for names in FIGURES_MAPS_BY_PAIR for name in names]
FIGURE_PARAMS = dict(  # what every figure states (analysis, interval, year), its scenario order and colours
    credible_interval = config["utility"]["credible_interval"],
    interval_type = config["utility"]["interval_type"],
    year = REFERENCE_YEAR,
    order = FIGURES_CONFIG["scenario_order"],
    highlight = FIGURES_CONFIG["highlight_scenarios"],
    ticino = TICINO,
    scenario_ids = list(SCENARIOS),
    # price basis of the footers and the reference-price axis (price.cost_scope)
    price_label = (f"energy price p_ref {ENERGY_REFERENCE['reference']} Rp./kWh (BFE GEST {REFERENCE_YEAR})"
                   if COST_SCOPE == "energy" else "ElCom prices"),
    price_axis = ("Energy reference price p_ref (Rp./kWh of final energy)" if COST_SCOPE == "energy"
                  else "ElCom reference price, total (Rp./kWh)"),
    # coefficients of the regional analysis: one Swiss set of the choice model, or per language region with TI
    coefficients_label = (f"Swiss coefficients of choice model {config['data']['choice_model']}"
                          if len(set(CHOICE_MODEL["coefficients"].values())) == 1 else None),
)
PAIRWISE_FORMATS = PNG_PDF
REGIONAL_OUTPUTS = [  # part of rule all only with spatial.resolution: regional
    "build/data/utility_rankings_regional.csv",
    "build/data/sensitivity/reference_price_curve_regional.csv",
    "build/data/sensitivity/reference_price_rank1_switches_regional.csv",
    "build/data/sensitivity/cost_scale_curve_regional.csv",
    "build/data/weather/weather_year_rankings.csv",
    *expand(FIGURE_PATH, figure="fig11_rank_by_weather_year_regional", fmt=PNG_PDF),
    *expand(FIGURE_PATH, figure=FIGURES_REGIONAL, fmt=FIGURE_FORMATS),
    *expand(FIGURE_PATH, figure=[FIGURE_PAIRWISE, *FIGURES_MAPS], fmt=PAIRWISE_FORMATS),
]


rule all:
    message: "Run entire analysis and tests."
    input:
        "build/data/utility_rankings.csv",
        expand(FIGURE_PATH, figure=FIGURES, fmt=FIGURE_FORMATS),
        "build/data/sensitivity/reference_price_curve.csv",
        expand(FIGURE_PATH, figure=FIGURE_SENSITIVITY, fmt=FIGURE_FORMATS),
        REGIONAL_OUTPUTS if config["spatial"]["resolution"] == "regional" else [],
        "build/test.success"


# Per year ({year} wildcard): the main chain requests price.reference_year, the sensitivity
# analysis additionally the base years.
rule fetch_eur_chf:
    message: "Fetch annual mean ECB EUR/CHF rate of {wildcards.year}."
    params: year = lambda wildcards: int(wildcards.year)
    output: "build/data/reference/eur_chf_{year}.json"
    wildcard_constraints:
        year = r"\d{4}"
    log: "build/logs/fetch_eur_chf_{year}.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_eur_chf.py"


rule fetch_elcom_reference:
    message: "Fetch ElCom reference price {wildcards.year} ({params.category})."
    params:
        year = lambda wildcards: int(wildcards.year),
        category = config["price"]["category"]
    output: "build/data/reference/elcom_price_{year}.json"
    wildcard_constraints:
        year = r"\d{4}"
    log: "build/logs/fetch_elcom_reference_{year}.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_elcom.py"


rule fetch_elcom_municipal:
    message: "Fetch ElCom tariff rows of all municipalities {wildcards.year} ({params.category})."
    params:
        year = lambda wildcards: int(wildcards.year),
        category = config["price"]["category"]
    output: "build/data/reference/elcom_municipal_{year}.csv"
    wildcard_constraints:
        year = r"\d{4}"
    log: "build/logs/fetch_elcom_municipal_{year}.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_elcom_municipal.py"


rule fetch_municipality_cantons:
    message: "Fetch municipality -> canton assignment (LINDAS register)."
    output: "build/data/reference/municipality_cantons.csv"
    log: "build/logs/fetch_municipality_cantons.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_municipality_cantons.py"


rule fetch_statpop:
    message: "Fetch STATPOP population per municipality, 31 Dec {wildcards.year}."
    params:
        year = lambda wildcards: int(wildcards.year),
        table = REGIONAL["statpop_table"]
    output: "build/data/reference/statpop_{year}.csv"
    wildcard_constraints:
        year = r"\d{4}"
    log: "build/logs/fetch_statpop_{year}.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_statpop.py"


rule scenario_attributes:
    message: "Compute choice-model attributes of scenario {wildcards.scenario} (land: {params.land_definition})."
    params:
        settings = MODEL_SETTINGS,
        land_definition = config["land"]["definition"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN,
        imports = IMPORTS
    input:
        src = src_modules("scripts/scenario_attributes.py"),
        nc = lambda wildcards: SCENARIO_DIR / SCENARIOS[wildcards.scenario],
        canton_area = config["data"]["canton_area"],
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        elcom = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json"
    output: "build/data/attributes/{scenario}.csv"
    wildcard_constraints:
        scenario = "|".join(SCENARIOS)
    log: "build/logs/scenario_attributes_{scenario}.log"
    conda: "envs/default.yaml"
    script: "scripts/scenario_attributes.py"


rule compute_attributes:
    message: "Combine attributes of all scenarios."
    input: expand("build/data/attributes/{scenario}.csv", scenario=SCENARIOS)
    output: "build/data/scenario_attributes_summary.csv"
    log: "build/logs/compute_attributes.log"
    conda: "envs/default.yaml"
    script: "scripts/combine_attributes.py"


rule compute_utility:
    message: "Compute utilities, credible intervals and rankings per language region (mobile_share={params.mobile_share})."
    params:
        settings = MODEL_SETTINGS,
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        src = src_modules("scripts/compute_utility.py"),
        attributes = rules.compute_attributes.output[0],
        choice_model = CHOICE_MODEL["file"]
    output: "build/data/utility_rankings.csv"
    log: "build/logs/compute_utility.log"
    conda: "envs/default.yaml"
    script: "scripts/compute_utility.py"


rule import_shares:
    message: "Import attribute per scenario: electricity, + fuels, + synthetic diesel (definition used: {params.definition})."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        fuel_techs = config["imports"]["fuel_techs"],
        diesel_techs = config["imports"]["diesel_techs"],
        definition = config["imports"]["definition"],
        denominator = config["imports"]["denominator"]
    input:
        src = src_modules("scripts/import_shares.py"),
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS]
    output: "build/data/regional/import_shares_regional.csv"
    log: "build/logs/import_shares.log"
    conda: "envs/default.yaml"
    script: "scripts/import_shares.py"


rule regional_reference:
    message: "Regional reference values per Calliope region: ElCom medians and population."
    params:
        settings = MODEL_SETTINGS,
        overrides = REGIONAL["municipality_canton_overrides"]
    input:
        src = src_modules("scripts/regional_reference.py"),
        prices = f"build/data/reference/elcom_municipal_{REFERENCE_YEAR}.csv",
        cantons = rules.fetch_municipality_cantons.output[0],
        statpop = f"build/data/reference/statpop_{REGIONAL['population_year']}.csv"
    output:
        elcom = "build/data/regional/elcom_by_region.csv",
        population = "build/data/regional/population_by_region.csv"
    log: "build/logs/regional_reference.log"
    conda: "envs/default.yaml"
    script: "scripts/regional_reference.py"


rule regional_attributes:
    message: "Attributes per Calliope region (regional analysis)."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        import_definition = config["imports"]["definition"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN
    input:
        src = src_modules("scripts/regional_attributes.py"),
        imports = rules.import_shares.output[0],
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS],
        canton_area = config["data"]["canton_area"],
        national = rules.compute_attributes.output[0],
        elcom = rules.regional_reference.output.elcom,
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json"
    output:
        attributes = "build/data/regional/regional_attributes.csv"
    log: "build/logs/regional_attributes.log"
    conda: "envs/default.yaml"
    script: "scripts/regional_attributes.py"


rule regional_utility:
    message: "Regional main analysis, sensitivities and checks (excluded regions: {params.exclude})."
    params:
        settings = MODEL_SETTINGS,
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        excluded_coefficients = REGIONAL["excluded_region_coefficients"],
        overrides = REGIONAL["municipality_canton_overrides"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        src = src_modules("scripts/regional_utility.py"),
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_reference.output.population,
        national = rules.compute_attributes.output[0],
        choice_model = CHOICE_MODEL["file"],
        canton_area = config["data"]["canton_area"],
        cantons = rules.fetch_municipality_cantons.output[0],
        statpop = f"build/data/reference/statpop_{REGIONAL['population_year']}.csv",
        imports = rules.import_shares.output[0]
    output:
        rankings = "build/data/utility_rankings_regional.csv",
        regions = "build/data/regional/region_rankings_regional.csv",
        rank1_share = "build/data/regional/rank1_population_share_regional.csv",
        sensitivities = "build/data/regional/sensitivity_regional.csv",
        checks = "build/data/regional/checks_regional.csv"
    log: "build/logs/regional_utility.log"
    conda: "envs/default.yaml"
    script: "scripts/regional_utility.py"


rule regional_reference_price:
    message: "Regional reference-price sweep (common shift of all regional reference prices)."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        shift = REGIONAL["reference_price_shift"],
        tolerance = SENSITIVITY["crossing_tolerance"],
        check_delta = SENSITIVITY["crossing_check_delta"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN
    input:
        src = src_modules("scripts/regional_reference_price.py"),
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_reference.output.population,
        elcom = rules.regional_reference.output.elcom,
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS],
        choice_model = CHOICE_MODEL["file"]
    output:
        curve = "build/data/sensitivity/reference_price_curve_regional.csv",
        switches = "build/data/sensitivity/reference_price_rank1_switches_regional.csv"
    log: "build/logs/regional_reference_price.log"
    conda: "envs/default.yaml"
    script: "scripts/regional_reference_price.py"


rule cost_scale_regional:
    message: "Sensitivity of the regional analysis to a common factor on the system cost ({params.factors})."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        factors = SENSITIVITY["cost_scale_factors"],
        conversions = SENSITIVITY["cost_scale_conversions"],
        search = SENSITIVITY["cost_scale_search"],
        tolerance = SENSITIVITY["crossing_tolerance"],
        check_delta = SENSITIVITY["crossing_check_delta"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN
    input:
        src = src_modules("scripts/cost_scale_regional.py"),
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_reference.output.population,
        elcom = rules.regional_reference.output.elcom,
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS],
        choice_model = CHOICE_MODEL["file"]
    output:
        curve = "build/data/sensitivity/cost_scale_curve_regional.csv",
        switches = "build/data/sensitivity/cost_scale_rank1_switches_regional.csv"
    log: "build/logs/cost_scale_regional.log"
    conda: "envs/default.yaml"
    script: "scripts/cost_scale_regional.py"


rule cost_groups:
    message: "System cost per cost group (electricity, other) and simulated price with all and with electricity costs."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        cost_groups = COST_GROUPS,
        fuel_power_techs = config["price"]["fuel_power_techs"],
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN,
        fuel_techs = config["imports"]["fuel_techs"],
        diesel_techs = config["imports"]["diesel_techs"],
        cost_scale = COST_SCALE
    input:
        src = src_modules("scripts/cost_groups.py"),
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS],
        elcom = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json"
    output:
        groups = "build/data/cost_groups.csv",
        technologies = "build/data/cost_by_technology.csv",
        power_fuel = "build/data/power_fuel_cost.csv",
        final_energy = "build/data/final_energy.csv"
    log: "build/logs/cost_groups.log"
    conda: "envs/default.yaml"
    script: "scripts/cost_groups.py"


rule weather_year_rankings:
    message: "Regional analysis for weather year {wildcards.year} (scenarios with a result file for that year)."
    params:
        settings = MODEL_SETTINGS,
        year = lambda wildcards: int(wildcards.year),
        scenario_ids = lambda wildcards: list(SCENARIOS_BY_YEAR[int(wildcards.year)]),
        common_scenarios = COMMON_SCENARIOS,
        land_definition = config["land"]["definition"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN,
        import_definition = config["imports"]["definition"],
        import_denominator = config["imports"]["denominator"],
        fuel_techs = config["imports"]["fuel_techs"],
        diesel_techs = config["imports"]["diesel_techs"],
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        src = src_modules("scripts/weather_year_rankings.py"),
        nc = lambda wildcards: [scenario_dir(int(wildcards.year)) / f for f in SCENARIOS_BY_YEAR[int(wildcards.year)].values()],
        canton_area = config["data"]["canton_area"],
        elcom_national = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        elcom_regional = rules.regional_reference.output.elcom,
        population = rules.regional_reference.output.population,
        choice_model = CHOICE_MODEL["file"]
    output:
        national = "build/data/weather/{year}/scenario_attributes_summary.csv",
        attributes = "build/data/weather/{year}/regional_attributes.csv",
        rankings = "build/data/weather/{year}/utility_rankings_regional.csv",
        rankings_common = "build/data/weather/{year}/utility_rankings_common_regional.csv"
    wildcard_constraints:
        year = "|".join(str(y) for y in WEATHER_YEARS)
    log: "build/logs/weather_year_rankings_{year}.log"
    conda: "envs/default.yaml"
    script: "scripts/weather_year_rankings.py"


rule weather_year_summary:
    message: "Compare the weather years {params.weather_years}."
    params:
        settings = MODEL_SETTINGS,
        weather_years = WEATHER_YEARS,
        scenarios = config["scenarios"]
    input:
        src = src_modules("scripts/weather_year_summary.py"),
        rankings = expand("build/data/weather/{year}/utility_rankings_regional.csv", year=WEATHER_YEARS),
        rankings_common = expand("build/data/weather/{year}/utility_rankings_common_regional.csv", year=WEATHER_YEARS)
    output:
        summary = "build/data/weather/weather_year_rankings.csv",
        missing = "build/data/weather/missing_runs.csv"
    log: "build/logs/weather_year_summary.log"
    conda: "envs/default.yaml"
    script: "scripts/weather_year_summary.py"


rule plot_weather_years:
    message: "Create the figure of the rank per weather year."
    params:
        settings = MODEL_SETTINGS,
        weather_years = WEATHER_YEARS,
        weather_year = WEATHER_YEAR,
        formats = PNG_PDF,
        **{**FIGURE_PARAMS, "scenario_ids": list(config["scenarios"])}
    input:
        src = src_modules("scripts/make_weather_year_plot.py"),
        summary = rules.weather_year_summary.output.summary
    output: expand(FIGURE_PATH, figure="fig11_rank_by_weather_year_regional", fmt=PNG_PDF)
    log: "build/logs/plot_weather_years.log"
    conda: "envs/default.yaml"
    script: "scripts/make_weather_year_plot.py"


rule beta_real_units:
    message: "Choice-model coefficients in real units (beta / sigma)."
    params:
        settings = MODEL_SETTINGS,
        mobile_share = config["utility"]["mobile_share"],
        coefficients = CHOICE_MODEL["coefficients"],
        cost_scope = COST_SCOPE,  # unit texts of cost and import
        import_definition = config["imports"]["definition"],
        import_denominator = config["imports"]["denominator"]
    input:
        choice_model = CHOICE_MODEL["file"],
        src = src_modules("scripts/beta_real_units.py")
    output:
        table = "build/data/beta_real_units.csv",
        check = "build/data/choice_model_check.csv"
    log: "build/logs/beta_real_units.log"
    conda: "envs/default.yaml"
    script: "scripts/beta_real_units.py"


rule make_plots:
    message: "Create figures of the national aggregate (appendix, mobile_share={params.mobile_share})."
    params:
        settings = MODEL_SETTINGS,
        mobile_share = config["utility"]["mobile_share"],
        **FIGURE_PARAMS
    input:
        src = src_modules("scripts/make_plots.py"),
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        choice_model = CHOICE_MODEL["file"]  # fig3/fig5 need the betas directly
    output:
        figures = expand(FIGURE_PATH, figure=FIGURES, fmt=FIGURE_FORMATS),
        contributions = "build/data/contributions_national.csv"
    log: "build/logs/make_plots.log"
    conda: "envs/default.yaml"
    script: "scripts/make_plots.py"


rule make_plots_regional:
    message: "Create figures of the regional main analysis."
    params:
        settings = MODEL_SETTINGS,
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        mobile_share = config["utility"]["mobile_share"],
        # fig6 top axis: national reference price (cost_scope energy: p_ref; otherwise the ElCom median, input elcom)
        reference_price = ENERGY_REFERENCE["reference"] if COST_SCOPE == "energy" else None,
        **FIGURE_PARAMS
    input:
        src = src_modules("scripts/make_plots_regional.py"),
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_reference.output.population,
        rankings = rules.regional_utility.output.rankings,
        regions = rules.regional_utility.output.regions,
        rank1_share = rules.regional_utility.output.rank1_share,
        curve = rules.regional_reference_price.output.curve,
        switches = rules.regional_reference_price.output.switches,
        elcom = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",  # national median, fig6 top axis
        choice_model = CHOICE_MODEL["file"]
    output:
        figures = expand(FIGURE_PATH, figure=FIGURES_REGIONAL, fmt=FIGURE_FORMATS),
        contributions = "build/data/regional/contributions_regional.csv"
    log: "build/logs/make_plots_regional.log"
    conda: "envs/default.yaml"
    script: "scripts/make_plots_regional.py"


rule pairwise_regional:
    message: "Pairwise choice probabilities of the regional analysis (matrix and map pairs)."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        exclude = EXCLUDE,
        coefficient_overrides = COEFFICIENT_OVERRIDES,
        order = FIGURES_CONFIG["scenario_order"],
        map_pairs = PAIRWISE["map_pairs"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        src = src_modules("scripts/pairwise_regional.py"),
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_reference.output.population,
        choice_model = CHOICE_MODEL["file"]
    output:
        matrix = "build/data/pairwise/pairwise_matrix_regional.csv",
        regions = "build/data/pairwise/pairwise_regions_regional.csv",
        map_tables = expand("build/data/pairwise/choice_map_{pair}_regional.csv", pair=MAP_PAIRS),
        comparison = "build/data/pairwise/aggregation_comparison_regional.csv",
        checks = "build/data/pairwise/checks_pairwise_regional.csv"
    log: "build/logs/pairwise_regional.log"
    conda: "envs/default.yaml"
    script: "scripts/pairwise_regional.py"


rule plot_pairwise:
    message: "Create the pairwise choice probability matrix."
    params:
        settings = MODEL_SETTINGS,
        decimals = PAIRWISE["decimals"],
        formats = PAIRWISE_FORMATS,
        **FIGURE_PARAMS
    input:
        src = src_modules("scripts/make_pairwise_plot.py"),
        matrix = rules.pairwise_regional.output.matrix,
        attributes = rules.regional_attributes.output.attributes
    output: expand(FIGURE_PATH, figure=FIGURE_PAIRWISE, fmt=PAIRWISE_FORMATS)
    log: "build/logs/plot_pairwise.log"
    conda: "envs/default.yaml"
    script: "scripts/make_pairwise_plot.py"


rule fetch_boundaries:
    message: "Download swisstopo swissBOUNDARIES3D (fixed release, checksum verified)."
    params:
        url = MAPS["boundaries"]["url"],
        sha256 = MAPS["boundaries"]["sha256"]
    output: MAPS["boundaries"]["file"]
    log: "build/logs/fetch_boundaries.log"
    conda: "envs/default.yaml"
    script: "scripts/fetch_boundaries.py"


rule choice_maps:
    message: "Create the maps of the regional choice probabilities."
    params:
        settings = MODEL_SETTINGS,
        boundaries = MAPS["boundaries"],
        crs = MAPS["crs"],
        tolerance = MAPS["simplify_tolerance_m"],
        exclude = EXCLUDE,
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        ticino = TICINO,
        year = REFERENCE_YEAR,
        price_label = FIGURE_PARAMS["price_label"],
        coefficients_label = FIGURE_PARAMS["coefficients_label"],
        names = FIGURES_MAPS_BY_PAIR,
        color_ranges = MAP_RANGES,
        formats = PAIRWISE_FORMATS
    input:
        src = src_modules("scripts/make_choice_maps.py"),
        boundaries = rules.fetch_boundaries.output[0],
        population = rules.regional_reference.output.population,
        tables = rules.pairwise_regional.output.map_tables
    output:
        checks = "build/data/pairwise/geometry_checks_regional.csv",
        figures = expand(FIGURE_PATH, figure=FIGURES_MAPS, fmt=PAIRWISE_FORMATS)
    log: "build/logs/choice_maps.log"
    conda: "envs/maps.yaml"
    script: "scripts/make_choice_maps.py"


rule sensitivity_reference_price:
    message: "Sensitivity to the ElCom reference price: curve, crossing points, base years {params.base_years}."
    params:
        settings = MODEL_SETTINGS,
        scenario_ids = list(SCENARIOS),
        reference_year = REFERENCE_YEAR,
        base_years = SENSITIVITY["base_years"],
        reference_price = SENSITIVITY["reference_price"],
        crossing_scenarios = SENSITIVITY["crossing_scenarios"],
        crossing_tolerance = SENSITIVITY["crossing_tolerance"],
        crossing_check_delta = SENSITIVITY["crossing_check_delta"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        cost_groups = COST_GROUPS,
        power_fuel = POWER_FUEL,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN
    input:
        src = src_modules("scripts/sensitivity_reference_price.py"),
        attributes = rules.compute_attributes.output[0],
        choice_model = CHOICE_MODEL["file"],
        nc = [SCENARIO_DIR / SCENARIOS[s] for s in SCENARIOS],
        elcom = expand("build/data/reference/elcom_price_{year}.json", year=SENSITIVITY_YEARS),
        eur_chf = expand("build/data/reference/eur_chf_{year}.json", year=SENSITIVITY_YEARS)
    output:
        curve = "build/data/sensitivity/reference_price_curve.csv",
        crossings = "build/data/sensitivity/reference_price_crossing_points.csv",
        base_years = "build/data/sensitivity/reference_price_base_years.csv",
        switches = "build/data/sensitivity/reference_price_rank1_switches.csv"
    log: "build/logs/sensitivity_reference_price.log"
    conda: "envs/default.yaml"
    script: "scripts/sensitivity_reference_price.py"


rule plot_sensitivity:
    message: "Create figure P(rank 1) vs. reference price."
    params:
        settings = MODEL_SETTINGS,
        **FIGURE_PARAMS
    input:
        src = src_modules("scripts/make_sensitivity_plot.py"),
        curve = rules.sensitivity_reference_price.output.curve,
        crossings = rules.sensitivity_reference_price.output.crossings,
        base_years = rules.sensitivity_reference_price.output.base_years,
        switches = rules.sensitivity_reference_price.output.switches
    output: expand(FIGURE_PATH, figure=FIGURE_SENSITIVITY, fmt=FIGURE_FORMATS)
    log: "build/logs/plot_sensitivity.log"
    conda: "envs/default.yaml"
    script: "scripts/make_sensitivity_plot.py"


rule dag_dot:
    message: "Rule graph of the workflow (snakemake --rulegraph, with the Python running this workflow)."
    output: temp("build/dag.dot")
    log: "build/logs/dag_dot.log"
    run: shell('"{sys.executable}" -m snakemake --rulegraph > {output} 2> {log}')


rule dag:
    message: "Plot dependency graph of the workflow."
    input: rules.dag_dot.output[0]
    # Output is deliberately omitted so rule is executed each time.
    log: "build/logs/dag.log"
    conda: "envs/dag.yaml"
    shell:
        "dot -Tpdf {input} -o build/dag.pdf 2> {log}"


rule pipeline_map_dot:
    message: "Simplified rule graphs for the pipeline map (all rules, regional main analysis)."
    params:
        settings = MODEL_SETTINGS
    input:
        src = src_modules("scripts/pipeline_map.py"),
        rulegraph = rules.dag_dot.output[0],
        texts = "docs/pipeline_map.yaml"
    output:
        full = temp("build/pipeline_map_full.dot"),
        regional = temp("build/pipeline_map_regional.dot")
    log: "build/logs/pipeline_map_dot.log"
    conda: "envs/default.yaml"
    script: "scripts/pipeline_map.py"


rule pipeline_map_graph:
    message: "Draw the pipeline map graphs with graphviz (as snakemake dag), without detours (tred)."
    input:
        full = rules.pipeline_map_dot.output.full,
        regional = rules.pipeline_map_dot.output.regional
    output:
        full = temp("build/pipeline_map_full.svg"),
        regional = temp("build/pipeline_map_regional.svg")
    log: "build/logs/pipeline_map_graph.log"
    conda: "envs/dag.yaml"
    shell:
        "(tred {input.full} | dot -Tsvg -o {output.full} && tred {input.regional} | dot -Tsvg -o {output.regional}) 2> {log}"


rule pipeline_map:
    message: "Interactive pipeline map (open build/pipeline_map.html in a browser)."
    params:
        settings = MODEL_SETTINGS,
        ticino = TICINO,
        choice_model_coefficients = CHOICE_MODEL["coefficients"],
        price_year = REFERENCE_YEAR,
        price_category = config["price"]["category"],
        base_years = SENSITIVITY["base_years"],
        curve_start = SENSITIVITY["reference_price"]["start"],
        curve_stop = SENSITIVITY["reference_price"]["stop"],
        population_year = REGIONAL["population_year"],
        weather_years = WEATHER_YEARS,
        exclude = EXCLUDE,
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        import_definition = config["imports"]["definition"],
        land_definition = config["land"]["definition"],
        boundaries_url = MAPS["boundaries"]["url"],
        map_pairs = PAIRWISE["map_pairs"],
        map_range = MAPS["color_range"],
        map_range_variant = MAPS["color_range_variant"],
        test_report = TEST_REPORT  # log of rule test
    input:
        src = src_modules("scripts/pipeline_map.py"),
        rulegraph = rules.dag_dot.output[0],
        graph_full = rules.pipeline_map_graph.output.full,
        graph_regional = rules.pipeline_map_graph.output.regional,
        texts = "docs/pipeline_map.yaml",
        template = "docs/pipeline_map_template.html",
        # results the numbers in the texts are read from
        elcom_national = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        elcom_regions = rules.regional_reference.output.elcom,
        population = rules.regional_reference.output.population,
        attributes = rules.compute_attributes.output[0],
        base_years = rules.sensitivity_reference_price.output.base_years,
        switches_regional = rules.regional_reference_price.output.switches,
        import_shares = rules.import_shares.output[0],
        pairwise_matrix = rules.pairwise_regional.output.matrix,
        missing_runs = rules.weather_year_summary.output.missing,
        choice_model = CHOICE_MODEL["file"],
        tests = "build/test.success"
    output: "build/pipeline_map.html"
    log: "build/logs/pipeline_map.log"
    conda: "envs/default.yaml"
    script: "scripts/pipeline_map.py"


rule clean: # removes all generated results
    message: "Remove all build results but keep downloaded data."
    log: "build/logs/clean.log"
    conda: "envs/default.yaml"
    script: "scripts/clean.py"

rule test:
    # Regression test against the frozen references in data/processed/.
    # To add more tests, do
    # (1) Add to-be-tested workflow outputs as inputs to this rule.
    # (2) Turn them into pytest fixtures in tests/test_runner.py.
    # (3) Create or reuse a test file in tests/my-test.py and use fixtures in tests.
    message: "Run tests"
    params:
        settings = MODEL_SETTINGS,
        import_definition = config["imports"]["definition"],
        cost_scale = COST_SCALE,
        cost_scope = COST_SCOPE,
        energy_reference = ENERGY_REFERENCE,
        margin = MARGIN,
        choice_model_coefficients = CHOICE_MODEL["coefficients"],
        weather_years = WEATHER_YEARS,
        weather_scenarios = {y: list(SCENARIOS_BY_YEAR[y]) for y in WEATHER_YEARS},
        common_scenarios = COMMON_SCENARIOS,
        import_denominator = config["imports"]["denominator"],
        cost_scale_factors = SENSITIVITY["cost_scale_factors"],
        cost_scale_conversions = SENSITIVITY["cost_scale_conversions"],
        cost_scale_search = SENSITIVITY["cost_scale_search"],
        ticino = TICINO
    input:
        test_dir = "tests",
        tests = map(str, Path("tests").glob("**/test_*.py")),
        src = src_modules(*Path("tests").glob("test_*.py")),
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        beta_real_units = rules.beta_real_units.output.table,
        choice_model_check = rules.beta_real_units.output.check,
        regional_attributes = rules.regional_attributes.output.attributes,
        regional_checks = rules.regional_utility.output.checks,
        pairwise_matrix = rules.pairwise_regional.output.matrix,
        pairwise_regions = rules.pairwise_regional.output.regions,
        pairwise_map_tables = rules.pairwise_regional.output.map_tables,
        pairwise_checks = rules.pairwise_regional.output.checks,
        geometry_checks = rules.choice_maps.output.checks,
        contributions_national = rules.make_plots.output.contributions,
        contributions_regional = rules.make_plots_regional.output.contributions,
        population_by_region = rules.regional_reference.output.population,
        elcom_by_region = rules.regional_reference.output.elcom,
        aggregation_comparison_regional = rules.pairwise_regional.output.comparison,
        import_shares_regional = rules.import_shares.output[0],
        reference_import_shares_regional = config["reference"]["import_shares_regional"],
        reference_population_by_region = config["reference"]["population_by_region"],
        reference_elcom_by_region = config["reference"]["elcom_by_region"],
        reference_pairwise_matrix_regional = config["reference"]["pairwise_matrix_regional"],
        reference_pairwise_regions_regional = config["reference"]["pairwise_regions_regional"],
        reference_aggregation_comparison_regional = config["reference"]["aggregation_comparison_regional"],
        reference_contributions_regional = config["reference"]["contributions_regional"],
        reference_contributions_national = config["reference"]["contributions_national"],
        rankings_regional = rules.regional_utility.output.rankings,
        region_rankings_regional = rules.regional_utility.output.regions,
        rank1_share_regional = rules.regional_utility.output.rank1_share,
        sensitivities_regional = rules.regional_utility.output.sensitivities,
        sensitivity_curve_regional = rules.regional_reference_price.output.curve,
        sensitivity_switches_regional = rules.regional_reference_price.output.switches,
        cost_scale_curve_regional = rules.cost_scale_regional.output.curve,
        cost_scale_switches_regional = rules.cost_scale_regional.output.switches,
        weather_summary = rules.weather_year_summary.output.summary,
        weather_missing = rules.weather_year_summary.output.missing,
        weather_rankings_main = f"build/data/weather/{WEATHER_YEAR}/utility_rankings_regional.csv",
        weather_regional_attributes = expand("build/data/weather/{year}/regional_attributes.csv", year=WEATHER_YEARS),
        reference_weather_rankings = config["reference"]["weather_rankings"],
        reference_weather_missing_runs = config["reference"]["weather_missing_runs"],
        reference_weather_regional_attributes = expand(config["reference"]["weather_regional_attributes"],
                                                       year=WEATHER_YEARS),
        cost_groups = rules.cost_groups.output.groups,
        cost_by_technology = rules.cost_groups.output.technologies,
        power_fuel_cost = rules.cost_groups.output.power_fuel,
        final_energy = rules.cost_groups.output.final_energy,
        elcom_national = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        reference_regional_attributes = config["reference"]["regional_attributes"],
        reference_rankings_regional = config["reference"]["rankings_regional"],
        reference_region_rankings_regional = config["reference"]["region_rankings_regional"],
        reference_rank1_share_regional = config["reference"]["rank1_share_regional"],
        reference_sensitivities_regional = config["reference"]["sensitivities_regional"],
        reference_sensitivity_curve_regional = config["reference"]["sensitivity_curve_regional"],
        reference_sensitivity_switches_regional = config["reference"]["sensitivity_switches_regional"],
        reference_attributes = config["reference"]["attributes"],
        reference_rankings = config["reference"]["rankings"],
        sensitivity_curve = rules.sensitivity_reference_price.output.curve,
        sensitivity_crossings = rules.sensitivity_reference_price.output.crossings,
        sensitivity_base_years = rules.sensitivity_reference_price.output.base_years,
        sensitivity_switches = rules.sensitivity_reference_price.output.switches,
        reference_sensitivity_curve = config["reference"]["sensitivity_curve"],
        reference_sensitivity_crossings = config["reference"]["sensitivity_crossings"],
        reference_sensitivity_base_years = config["reference"]["sensitivity_base_years"],
        reference_sensitivity_switches = config["reference"]["sensitivity_switches"],
        figure_sensitivity = expand(FIGURE_PATH, figure=FIGURE_SENSITIVITY, fmt=PNG_PDF),
        reference_figure_sensitivity = expand("{path}.{fmt}", path=config["reference"]["figure_sensitivity"], fmt=PNG_PDF)
    log: TEST_REPORT
    output: "build/test.success"
    conda: "envs/test.yaml"
    script: "tests/test_runner.py"
