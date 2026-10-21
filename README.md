# Predicting Citizen Preferences for Switzerland's Winter Electricity Deficit Mitigation Scenarios Using a Discrete Choice Model

Semester project mapping winter-gap mitigation energy scenarios from Mellot et al. (2024), *"Mitigating future winter electricity deficits: A case study from Switzerland"*, onto the discrete choice model from Tröndle, Mey & Lilliestam (2025), *"Socially preferable and technically feasible: European citizens choose solar power and import independence over lower costs"*, to predict Swiss citizen preferences.

**Author:** Josua Müller
**Supervision:** Dr. Tim Tröndle, Prof. Anthony Patt

## Overview

This project applies an existing discrete choice model (Tröndle, Mey & Lilliestam 2025), fitted on European stated-preference data, out-of-sample to Switzerland. The model's five attributes (dominant technology, land requirement, transmission capacity, import share, household price change) are mapped from Mellot et al.'s (2024) twelve winter-deficit mitigation scenarios, in order to rank them by predicted citizen utility and compare this ranking against Mellot et al.'s cost-optimal ranking.

## Data sources

| Source | Content | Link |
|---|---|---|
| Mellot et al. (2024) | Winter-deficit scenario data (Swiss-Calliope) | Zenodo, DOI 10.5281/zenodo.10887523 |
| Tröndle, Mey & Lilliestam (2025) | Fitted model coefficients (posterior inference, NetCDF) | Zenodo, DOI 10.5281/zenodo.14501018 |
| Tröndle, Mey & Lilliestam (2025) | Reproducible analysis code (Snakemake) | Zenodo, DOI 10.5281/zenodo.14501036 |

Large data files are **not** committed to this repository. Download them directly from the Zenodo links above into `data/raw/` (git-ignored).

## Run the analysis

The pipeline is a Snakemake workflow. You need [conda](https://conda.org); create the workflow environment once:

    conda env create -f environment.yaml --no-default-packages
    conda activate swiss-winter-deficit

Then run the entire workflow (attribute extraction -> utility -> figures -> regression tests):

    snakemake

Results go to `build/` (git-ignored). Each rule runs in its own conda environment (`envs/`), pinned to the versions the reference results were validated with. The rule `test` compares `build/` against the frozen reference results in `data/processed/`. Other useful rules: `snakemake --list`, `snakemake dag` (dependency graph as `build/dag.pdf`), `snakemake clean`.

The two live data sources are pinned in `config/default.yaml` by one base year (`price.reference_year`): the ElCom reference price of that year and the EUR/CHF rate as the annual mean of the daily ECB reference rates of the same year (the year must be completed). This file is the single source for these price parameters; `src/config.py` reads them from there, so notebooks and the pipeline use the same values.

If a Python virtual environment (e.g. `.venv`) is active, run `deactivate` first: otherwise its `python` shadows the rules' conda environments.

### Sensitivity to the reference price

The rule `sensitivity_reference_price` (`src/sensitivity.py`) checks how the ranking depends on the ElCom reference price, with the settings in the `sensitivity` section of `config/default.yaml`:

- a curve of rank and P(rank 1) of all scenarios over the reference price (default 20–35 Rp./kWh, step 0.25), with taxes/levies, grid usage and EUR/CHF rate of `price.reference_year`;
- the reference price at which Alpine PV and S/CCGT (Fossil) + DACCS swap rank, per language region and national;
- the real base years (default 2022–2025), each with its own ElCom reference values and annual EUR/CHF rate (the reference fetch rules run once per year).

Results go to `build/data/sensitivity/`, the figure to `build/figures/fig6_p_rank1_vs_reference_price.*` (rule `plot_sensitivity`). Both are part of `snakemake` (rule `all`) and of the regression tests; to run only this part: `snakemake build/figures/fig6_p_rank1_vs_reference_price.png`.

## Repository structure

```
.
├── Snakefile          # workflow definition
├── config/            # workflow configuration (scenario mapping, price reference, sensitivity)
├── envs/              # conda environments per rule
├── profiles/          # Snakemake execution profile (conda, 1 core)
├── scripts/           # thin Snakemake wrappers around src/
├── tests/             # regression tests against data/processed/ and graphics/ (fig6)
├── src/               # mapping and prediction library code
├── data/
│   ├── raw/           # downloaded Zenodo data (git-ignored)
│   └── processed/     # frozen, validated reference results
├── graphics/          # frozen thesis figures
├── legacy/            # first approach and exploratory notebooks (not maintained, see legacy/README.md)
└── build/             # workflow results (git-ignored)
```

The regression tests use `data/processed/scenario_attributes_summary.csv`,
`data/processed/utility_rankings.csv`, `data/processed/reference_price_*.csv` and
`graphics/fig6_p_rank1_vs_reference_price.{png,pdf}`. The other files in `data/processed/`
(`beta_real_units.csv`, `scenario_*.csv`) and `graphics/cost_vs_preference.png` are outdated
intermediate products of the first approach in `legacy/`.

## Status

Work in progress.
