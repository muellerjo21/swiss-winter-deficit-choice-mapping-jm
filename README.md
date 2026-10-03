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

The two live data sources are pinned in `config/default.yaml`: the ElCom reference price by year, the ECB EUR/CHF rate by date.

## Repository structure

```
.
├── Snakefile          # workflow definition
├── config/            # workflow configuration (scenario mapping, price reference)
├── envs/              # conda environments per rule
├── profiles/          # Snakemake execution profile (conda, 1 core)
├── scripts/           # thin Snakemake wrappers around src/
├── tests/             # regression tests against data/processed/
├── src/               # mapping and prediction library code
├── data/
│   ├── raw/           # downloaded Zenodo data (git-ignored)
│   ├── manual/        # manually compiled scenario data
│   └── processed/     # frozen, validated reference results
├── notebooks/         # exploratory analysis
├── graphics/          # frozen reference figures
└── build/             # workflow results (git-ignored)
```

## Status

Work in progress.
