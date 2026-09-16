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

Large data files (in particular `choice-model-inference.nc`, ~3.5 GB) are **not** committed to this repository. Download them directly from the Zenodo links above into `data/raw/` (git-ignored).

## Repository structure

```
.
├── data/
│   ├── raw/          # downloaded Zenodo data (git-ignored)
│   └── processed/    # mapped attribute values, intermediate outputs
├── src/               # mapping and prediction pipeline
├── notebooks/         # exploratory analysis
├── graphics/          # figures (e.g. mock comparison chart, Gantt chart)
└── README.md
```

## Status

Work in progress. See the project proposal (Overleaf) for the full method description and open methodological questions.
