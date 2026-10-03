from snakemake.utils import min_version
from pathlib import Path

configfile: "config/default.yaml"
min_version("9.6")

SCENARIOS = config["scenarios"]  # Szenario-ID -> .nc-Dateiname
FIGURES = [  # von src/make_graphics.make_all erzeugt
    "fig1_rank_choice_vs_cost", "fig2_utility_forest", "fig3_utility_contributions",
    "fig4_rank_de_vs_fr", "fig5_cost_vs_preference", "figA1_utility_contributions_absolute",
]
FIGURE_FORMATS = ["png", "pdf", "svg"]


rule all:
    message: "Run entire analysis and tests."
    input:
        "build/data/utility_rankings.csv",
        expand("build/figures/{figure}.{fmt}", figure=FIGURES, fmt=FIGURE_FORMATS),
        "build/test.success"


rule fetch_eur_chf:
    message: "Fetch ECB EUR/CHF reference rate of {params.date}."
    params: date = config["price"]["reference_date"]
    output: "build/data/reference/eur_chf.json"
    conda: "envs/default.yaml"
    script: "scripts/fetch_eur_chf.py"


rule fetch_elcom_reference:
    message: "Fetch ElCom reference price {params.year} ({params.category})."
    params:
        year = config["price"]["reference_year"],
        category = config["price"]["category"]
    output: "build/data/reference/elcom_price.json"
    conda: "envs/default.yaml"
    script: "scripts/fetch_elcom.py"


rule scenario_attributes:
    message: "Compute choice-model attributes of scenario {wildcards.scenario}."
    input:
        nc = lambda wildcards: Path(config["data"]["scenario_dir"]) / SCENARIOS[wildcards.scenario],
        canton_area = config["data"]["canton_area"],
        eur_chf = rules.fetch_eur_chf.output[0],
        elcom = rules.fetch_elcom_reference.output[0]
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
    message: "Compute utilities, credible intervals and rankings per language region."
    input:
        attributes = rules.compute_attributes.output[0],
        choice_model = config["data"]["choice_model"]
    output: "build/data/utility_rankings.csv"
    conda: "envs/default.yaml"
    script: "scripts/compute_utility.py"


rule make_plots:
    message: "Create figures."
    input:
        attributes = rules.compute_attributes.output[0],
        rankings = rules.compute_utility.output[0],
        choice_model = config["data"]["choice_model"]  # fig3/fig5 brauchen die Betas direkt
    output: expand("build/figures/{figure}.{fmt}", figure=FIGURES, fmt=FIGURE_FORMATS)
    conda: "envs/default.yaml"
    script: "scripts/make_plots.py"


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
    # Regressionstest gegen die eingefrorenen Referenzen in data/processed/.
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
        reference_rankings = config["reference"]["rankings"]
    log: "build/test-report.html"
    output: "build/test.success"
    conda: "envs/test.yaml"
    script: "tests/test_runner.py"
