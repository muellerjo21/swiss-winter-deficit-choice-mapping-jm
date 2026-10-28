from snakemake.utils import min_version
from pathlib import Path

configfile: "config/default.yaml"
min_version("9.6")

SCENARIOS = config["scenarios"]  # scenario ID -> .nc file name
FIGURES = [  # created by src/make_graphics.make_all
    "fig1_rank_choice_vs_cost", "fig2_utility_forest", "fig3_utility_contributions",
    "fig4_rank_de_vs_fr", "fig5_cost_vs_preference", "figA1_utility_contributions_absolute",
]
FIGURE_FORMATS = ["png", "pdf", "svg"]
FIGURE_PATH = "build/figures/{fmt}/{figure}.{fmt}"  # one subfolder per format
REFERENCE_YEAR = config["price"]["reference_year"]
SENSITIVITY = config["sensitivity"]
FIGURE_SENSITIVITY = "fig6_p_rank1_vs_reference_price"  # created by src/make_graphics.fig_reference_price_sensitivity
SENSITIVITY_YEARS = sorted(set(SENSITIVITY["base_years"]) | {REFERENCE_YEAR})
REGIONAL = config["spatial"]["regional"]
FIGURES_REGIONAL = [  # created by src/make_graphics.make_all_regional
    "fig1_rank_choice_vs_cost_regional", "fig2_utility_forest_regional", "fig3_utility_contributions_regional",
    "fig4_rank_de_vs_fr_regional", "fig5_cost_vs_preference_regional", "figA1_utility_contributions_absolute_regional",
    "fig6_p_rank1_vs_reference_price_shift_regional", "fig7_rank1_by_region_regional",
    "fig8_rank1_population_share_regional",
]
PAIRWISE = config["pairwise"]
MAPS = config["maps"]
MAP_PAIRS = [f"{a}_vs_{b}" for a, b in PAIRWISE["map_pairs"]]
FIGURE_PAIRWISE = "fig9_pairwise_choice_probability_regional"
FIGURES_MAPS = [f"fig10_choice_map_{pair}_regional" for pair in MAP_PAIRS]
PAIRWISE_FORMATS = ["png", "pdf"]
REGIONAL_OUTPUTS = [  # part of rule all only with spatial.resolution: regional
    "build/data/utility_rankings_regional.csv",
    "build/data/sensitivity/reference_price_curve_regional.csv",
    "build/data/sensitivity/reference_price_rank1_switches_regional.csv",
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
    conda: "envs/default.yaml"
    script: "scripts/fetch_elcom_municipal.py"


rule fetch_municipality_cantons:
    message: "Fetch municipality -> canton assignment (LINDAS register)."
    output: "build/data/reference/municipality_cantons.csv"
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
    conda: "envs/default.yaml"
    script: "scripts/fetch_statpop.py"


rule scenario_attributes:
    message: "Compute choice-model attributes of scenario {wildcards.scenario} (land: {params.land_definition})."
    params: land_definition = config["land"]["definition"]
    input:
        nc = lambda wildcards: Path(config["data"]["scenario_dir"]) / SCENARIOS[wildcards.scenario],
        canton_area = config["data"]["canton_area"],
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        elcom = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json"
    output: "build/data/attributes/{scenario}.csv"
    wildcard_constraints:
        scenario = "|".join(SCENARIOS)
    conda: "envs/default.yaml"
    script: "scripts/scenario_attributes.py"


rule compute_attributes:
    message: "Combine attributes of all scenarios."
    input: expand("build/data/attributes/{scenario}.csv", scenario=SCENARIOS)
    output: "build/data/scenario_attributes_summary.csv"
    conda: "envs/default.yaml"
    script: "scripts/combine_attributes.py"


rule compute_utility:
    message: "Compute utilities, credible intervals and rankings per language region (mobile_share={params.mobile_share})."
    params:
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.compute_attributes.output[0],
        choice_model = config["data"]["choice_model"]
    output: "build/data/utility_rankings.csv"
    conda: "envs/default.yaml"
    script: "scripts/compute_utility.py"


rule regional_attributes:
    message: "Attributes per Calliope region (regional analysis)."
    params:
        scenario_ids = list(SCENARIOS),
        overrides = REGIONAL["municipality_canton_overrides"]
    input:
        nc = [Path(config["data"]["scenario_dir"]) / SCENARIOS[s] for s in SCENARIOS],
        canton_area = config["data"]["canton_area"],
        national = rules.compute_attributes.output[0],
        prices = f"build/data/reference/elcom_municipal_{REFERENCE_YEAR}.csv",
        cantons = rules.fetch_municipality_cantons.output[0],
        statpop = f"build/data/reference/statpop_{REGIONAL['population_year']}.csv",
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json"
    output:
        attributes = "build/data/regional/regional_attributes.csv",
        elcom = "build/data/regional/elcom_by_region.csv",
        population = "build/data/regional/population_by_region.csv"
    conda: "envs/default.yaml"
    script: "scripts/regional_attributes.py"


rule regional_utility:
    message: "Regional main analysis, sensitivities and checks (excluded regions: {params.exclude})."
    params:
        exclude = REGIONAL["exclude_regions"],
        excluded_coefficients = REGIONAL["excluded_region_coefficients"],
        overrides = REGIONAL["municipality_canton_overrides"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_attributes.output.population,
        national = rules.compute_attributes.output[0],
        choice_model = config["data"]["choice_model"],
        canton_area = config["data"]["canton_area"],
        cantons = rules.fetch_municipality_cantons.output[0],
        statpop = f"build/data/reference/statpop_{REGIONAL['population_year']}.csv"
    output:
        rankings = "build/data/utility_rankings_regional.csv",
        regions = "build/data/regional/region_rankings_regional.csv",
        rank1_share = "build/data/regional/rank1_population_share_regional.csv",
        sensitivities = "build/data/regional/sensitivity_regional.csv",
        checks = "build/data/regional/checks_regional.csv"
    conda: "envs/default.yaml"
    script: "scripts/regional_utility.py"


rule regional_reference_price:
    message: "Regional reference-price sweep (common shift of all regional reference prices)."
    params:
        scenario_ids = list(SCENARIOS),
        exclude = REGIONAL["exclude_regions"],
        shift = REGIONAL["reference_price_shift"],
        tolerance = SENSITIVITY["crossing_tolerance"],
        check_delta = SENSITIVITY["crossing_check_delta"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_attributes.output.population,
        elcom = rules.regional_attributes.output.elcom,
        eur_chf = f"build/data/reference/eur_chf_{REFERENCE_YEAR}.json",
        nc = [Path(config["data"]["scenario_dir"]) / SCENARIOS[s] for s in SCENARIOS],
        choice_model = config["data"]["choice_model"]
    output:
        curve = "build/data/sensitivity/reference_price_curve_regional.csv",
        switches = "build/data/sensitivity/reference_price_rank1_switches_regional.csv"
    conda: "envs/default.yaml"
    script: "scripts/regional_reference_price.py"


rule beta_real_units:
    message: "Choice-model coefficients in real units (beta / sigma)."
    params: mobile_share = config["utility"]["mobile_share"]
    input: choice_model = config["data"]["choice_model"]
    output: "build/data/beta_real_units.csv"
    conda: "envs/default.yaml"
    script: "scripts/beta_real_units.py"


rule make_plots:
    message: "Create figures (mobile_share={params.mobile_share})."
    params:
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        choice_model = config["data"]["choice_model"]  # fig3/fig5 need the betas directly
    output: expand(FIGURE_PATH, figure=FIGURES, fmt=FIGURE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_plots.py"


rule make_plots_regional:
    message: "Create figures of the regional main analysis."
    params:
        exclude = REGIONAL["exclude_regions"],
        figure_scenarios = SENSITIVITY["figure_scenarios"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_attributes.output.population,
        rankings = rules.regional_utility.output.rankings,
        regions = rules.regional_utility.output.regions,
        rank1_share = rules.regional_utility.output.rank1_share,
        curve = rules.regional_reference_price.output.curve,
        switches = rules.regional_reference_price.output.switches,
        elcom = f"build/data/reference/elcom_price_{REFERENCE_YEAR}.json",  # national median, fig6 top axis
        choice_model = config["data"]["choice_model"]
    output: expand(FIGURE_PATH, figure=FIGURES_REGIONAL, fmt=FIGURE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_plots_regional.py"


rule pairwise_regional:
    message: "Pairwise choice probabilities of the regional analysis (matrix and map pairs)."
    params:
        scenario_ids = list(SCENARIOS),
        exclude = REGIONAL["exclude_regions"],
        order = PAIRWISE["scenario_order"],
        map_pairs = PAIRWISE["map_pairs"],
        mobile_share = config["utility"]["mobile_share"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"]
    input:
        attributes = rules.regional_attributes.output.attributes,
        population = rules.regional_attributes.output.population,
        choice_model = config["data"]["choice_model"]
    output:
        matrix = "build/data/pairwise/pairwise_matrix_regional.csv",
        regions = "build/data/pairwise/pairwise_regions_regional.csv",
        map_tables = expand("build/data/pairwise/choice_map_{pair}_regional.csv", pair=MAP_PAIRS),
        comparison = "build/data/pairwise/aggregation_comparison_regional.csv",
        checks = "build/data/pairwise/checks_pairwise_regional.csv"
    conda: "envs/default.yaml"
    script: "scripts/pairwise_regional.py"


rule plot_pairwise:
    message: "Create the pairwise choice probability matrix."
    params:
        order = PAIRWISE["scenario_order"],
        decimals = PAIRWISE["decimals"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        name = FIGURE_PAIRWISE,
        formats = PAIRWISE_FORMATS
    input:
        matrix = rules.pairwise_regional.output.matrix,
        attributes = rules.regional_attributes.output.attributes
    output: expand(FIGURE_PATH, figure=FIGURE_PAIRWISE, fmt=PAIRWISE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_pairwise_plot.py"


rule fetch_boundaries:
    message: "Download swisstopo swissBOUNDARIES3D (fixed release, checksum verified)."
    params:
        url = MAPS["boundaries"]["url"],
        sha256 = MAPS["boundaries"]["sha256"]
    output: MAPS["boundaries"]["file"]
    conda: "envs/default.yaml"
    script: "scripts/fetch_boundaries.py"


rule choice_maps:
    message: "Create the maps of the regional choice probabilities."
    params:
        boundaries = MAPS["boundaries"],
        crs = MAPS["crs"],
        tolerance = MAPS["simplify_tolerance_m"],
        exclude = REGIONAL["exclude_regions"],
        credible_interval = config["utility"]["credible_interval"],
        interval_type = config["utility"]["interval_type"],
        names = FIGURES_MAPS,
        formats = PAIRWISE_FORMATS,
        figure_dir = "build/figures"
    input:
        boundaries = rules.fetch_boundaries.output[0],
        population = rules.regional_attributes.output.population,
        tables = rules.pairwise_regional.output.map_tables
    output:
        checks = "build/data/pairwise/geometry_checks_regional.csv",
        figures = expand(FIGURE_PATH, figure=FIGURES_MAPS, fmt=PAIRWISE_FORMATS)
    conda: "envs/maps.yaml"
    script: "scripts/make_choice_maps.py"


rule sensitivity_reference_price:
    message: "Sensitivity to the ElCom reference price: curve, crossing points, base years {params.base_years}."
    params:
        scenario_ids = list(SCENARIOS),
        reference_year = REFERENCE_YEAR,
        base_years = SENSITIVITY["base_years"],
        reference_price = SENSITIVITY["reference_price"],
        crossing_scenarios = SENSITIVITY["crossing_scenarios"],
        crossing_tolerance = SENSITIVITY["crossing_tolerance"],
        crossing_check_delta = SENSITIVITY["crossing_check_delta"],
        mobile_share = config["utility"]["mobile_share"]
    input:
        attributes = rules.compute_attributes.output[0],
        choice_model = config["data"]["choice_model"],
        nc = [Path(config["data"]["scenario_dir"]) / SCENARIOS[s] for s in SCENARIOS],
        elcom = expand("build/data/reference/elcom_price_{year}.json", year=SENSITIVITY_YEARS),
        eur_chf = expand("build/data/reference/eur_chf_{year}.json", year=SENSITIVITY_YEARS)
    output:
        curve = "build/data/sensitivity/reference_price_curve.csv",
        crossings = "build/data/sensitivity/reference_price_crossing_points.csv",
        base_years = "build/data/sensitivity/reference_price_base_years.csv",
        switches = "build/data/sensitivity/reference_price_rank1_switches.csv"
    conda: "envs/default.yaml"
    script: "scripts/sensitivity_reference_price.py"


rule plot_sensitivity:
    message: "Create figure P(rank 1) vs. reference price."
    params:
        figure_scenarios = SENSITIVITY["figure_scenarios"]
    input:
        curve = rules.sensitivity_reference_price.output.curve,
        crossings = rules.sensitivity_reference_price.output.crossings,
        base_years = rules.sensitivity_reference_price.output.base_years,
        switches = rules.sensitivity_reference_price.output.switches
    output: expand(FIGURE_PATH, figure=FIGURE_SENSITIVITY, fmt=FIGURE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_sensitivity_plot.py"


rule dag_dot:
    output: temp("build/dag.dot")
    shell:
        "snakemake --rulegraph > {output}"


rule dag:
    message: "Plot dependency graph of the workflow."
    input: rules.dag_dot.output[0]
    # Output is deliberately omitted so rule is executed each time.
    conda: "envs/dag.yaml"
    shell:
        "dot -Tpdf {input} -o build/dag.pdf"


rule clean: # removes all generated results
    message: "Remove all build results but keep downloaded data."
    run:
         import shutil

         shutil.rmtree("build")
         print("Data in data/ (incl. frozen references in data/processed/) has not been cleaned.")


rule test:
    # Regression test against the frozen references in data/processed/.
    # To add more tests, do
    # (1) Add to-be-tested workflow outputs as inputs to this rule.
    # (2) Turn them into pytest fixtures in tests/test_runner.py.
    # (3) Create or reuse a test file in tests/my-test.py and use fixtures in tests.
    message: "Run tests"
    input:
        test_dir = "tests",
        tests = map(str, Path("tests").glob("**/test_*.py")),
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        beta_real_units = rules.beta_real_units.output[0],
        regional_attributes = rules.regional_attributes.output.attributes,
        regional_checks = rules.regional_utility.output.checks,
        pairwise_matrix = rules.pairwise_regional.output.matrix,
        pairwise_regions = rules.pairwise_regional.output.regions,
        pairwise_map_tables = rules.pairwise_regional.output.map_tables,
        pairwise_checks = rules.pairwise_regional.output.checks,
        geometry_checks = rules.choice_maps.output.checks,
        rankings_regional = rules.regional_utility.output.rankings,
        region_rankings_regional = rules.regional_utility.output.regions,
        rank1_share_regional = rules.regional_utility.output.rank1_share,
        sensitivities_regional = rules.regional_utility.output.sensitivities,
        sensitivity_curve_regional = rules.regional_reference_price.output.curve,
        sensitivity_switches_regional = rules.regional_reference_price.output.switches,
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
        figure_sensitivity = expand(FIGURE_PATH, figure=FIGURE_SENSITIVITY, fmt=["png", "pdf"]),
        reference_figure_sensitivity = expand("{path}.{fmt}", path=config["reference"]["figure_sensitivity"], fmt=["png", "pdf"])
    log: "build/test-report.html"
    output: "build/test.success"
    conda: "envs/test.yaml"
    script: "tests/test_runner.py"
