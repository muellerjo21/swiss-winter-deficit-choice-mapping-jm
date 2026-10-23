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
REFERENCE_YEAR = config["price"]["reference_year"]
SENSITIVITY = config["sensitivity"]
FIGURE_SENSITIVITY = "fig6_p_rank1_vs_reference_price"  # created by src/make_graphics.fig_reference_price_sensitivity
SENSITIVITY_YEARS = sorted(set(SENSITIVITY["base_years"]) | {REFERENCE_YEAR})


rule all:
    message: "Run entire analysis and tests."
    input:
        "build/data/utility_rankings.csv",
        expand("build/figures/{figure}.{fmt}", figure=FIGURES, fmt=FIGURE_FORMATS),
        "build/data/sensitivity/reference_price_curve.csv",
        expand("build/figures/{figure}.{fmt}", figure=FIGURE_SENSITIVITY, fmt=FIGURE_FORMATS),
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
    params: mobile_share = config["utility"]["mobile_share"]
    input:
        attributes = rules.compute_attributes.output[0],
        choice_model = config["data"]["choice_model"]
    output: "build/data/utility_rankings.csv"
    conda: "envs/default.yaml"
    script: "scripts/compute_utility.py"


rule make_plots:
    message: "Create figures (mobile_share={params.mobile_share})."
    params: mobile_share = config["utility"]["mobile_share"]
    input:
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        choice_model = config["data"]["choice_model"]  # fig3/fig5 need the betas directly
    output: expand("build/figures/{figure}.{fmt}", figure=FIGURES, fmt=FIGURE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_plots.py"


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
    output: expand("build/figures/{figure}.{fmt}", figure=FIGURE_SENSITIVITY, fmt=FIGURE_FORMATS)
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
        figure_sensitivity = expand("build/figures/{figure}.{fmt}", figure=FIGURE_SENSITIVITY, fmt=["png", "pdf"]),
        reference_figure_sensitivity = expand("{path}.{fmt}", path=config["reference"]["figure_sensitivity"], fmt=["png", "pdf"])
    log: "build/test-report.html"
    output: "build/test.success"
    conda: "envs/test.yaml"
    script: "tests/test_runner.py"
