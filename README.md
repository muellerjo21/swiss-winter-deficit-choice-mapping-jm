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
| swisstopo, swissBOUNDARIES3D, release 2025-01 | Canton boundaries for the maps (GeoPackage, LV95), downloaded by the rule `fetch_boundaries` with SHA-256 check | [data.geo.admin.ch](https://data.geo.admin.ch/ch.swisstopo.swissboundaries3d/swissboundaries3d_2025-01/swissboundaries3d_2025-01_2056_5728.gpkg.zip) |

**Licence of the boundaries.** swissBOUNDARIES3D is free geodata of the Federal Office of Topography swisstopo (open government data); use, also commercial, is free with source attribution: "Source: Federal Office of Topography swisstopo" / "© swisstopo". Terms of use: https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices. The figures credit swisstopo in their footnote. Release 2025-01 is the status of 1 January 2025 (Moutier still in Bern, consistent with STATPOP 2024).

Large data files are **not** committed to this repository. Download them directly from the Zenodo links above into `data/raw/` (git-ignored).

## Run the analysis

The pipeline is a Snakemake workflow. You need [conda](https://conda.org); create the workflow environment once:

    conda env create -f environment.yaml --no-default-packages
    conda activate swiss-winter-deficit

Then run the entire workflow (attribute extraction -> utility -> figures -> regression tests):

    snakemake

Results go to `build/` (git-ignored); figures in `build/figures/` with one subfolder per format (`png/`, `pdf/`, `svg/`). Each rule runs in its own conda environment (`envs/`), pinned to the versions the reference results were validated with. The rule `test` compares `build/` against the frozen reference results in `data/processed/`. Other useful rules: `snakemake --list`, `snakemake dag` (dependency graph as `build/dag.pdf`), `snakemake clean`.

`snakemake pipeline_map` writes an interactive map of the workflow to `build/pipeline_map.html` (open it in a browser): the rule graph drawn by graphviz as in `snakemake dag`; click a step to see what it does, what it needs and what it feeds, with the open points of the method. Texts in `docs/pipeline_map.yaml` (every rule needs an entry, otherwise the rule fails); the numbers in the texts are read from the results when the map is built.

The two live data sources are pinned in `config/default.yaml` by one base year (`price.reference_year`): the ElCom reference price of that year and the EUR/CHF rate as the annual mean of the daily ECB reference rates of the same year (the year must be completed). This file is the single source for these price parameters; `src/config.py` reads them from there, so notebooks and the pipeline use the same values.

In the national aggregate, the attribute `relative_land` (land used by wind and open-field PV) is by default the national share: national land use divided by the area of Switzerland (sum of the canton areas), like all other attributes national. The switch `land.definition` in `config/default.yaml` selects the previous definition `canton_mean` (unweighted mean of the cantons' shares, about twice as large for most scenarios) for comparison; the choice changes the ranking of the leading scenarios. In the regional main analysis it is the land share of the own region.

If a Python virtual environment (e.g. `.venv`) is active, run `deactivate` first: otherwise its `python` shadows the rules' conda environments.

### Sensitivity to the reference price

The rule `sensitivity_reference_price` (`src/sensitivity.py`) checks how the ranking depends on the ElCom reference price, with the settings in the `sensitivity` section of `config/default.yaml`:

- a curve of rank and P(rank 1) of all scenarios over the reference price (default 20–35 Rp./kWh, step 0.25), with taxes/levies, grid usage and EUR/CHF rate of `price.reference_year`;
- the reference price at which Alpine PV and S/CCGT (Fossil) + DACCS swap rank, per language region and national;
- the real base years (default 2022–2025), each with its own ElCom reference values and annual EUR/CHF rate (the reference fetch rules run once per year).

Fig6 marks the reference prices at which the rank-1 scenario changes (`reference_price_rank1_switches.csv`); the rank swap of the pair Alpine PV / S/CCGT (Fossil) + DACCS is kept as a separate CSV (`reference_price_crossing_points.csv`). Results go to `build/data/sensitivity/`, the figure to `build/figures/{png,pdf,svg}/fig6_p_rank1_vs_reference_price_national.*` (rule `plot_sensitivity`). Both are part of `snakemake` (rule `all`) and of the regression tests; to run only this part: `snakemake build/figures/png/fig6_p_rank1_vs_reference_price_national.png`.

### Regional analysis (main analysis)

The main analysis runs on the 23 Swiss locations of the Calliope model (20 cantons, the merged regions AI_AR, BL_BS and NW_OW, and TI; `src/regional.py`), set by `spatial.resolution: regional` in `config/default.yaml`:

- land use (regional area), technology and ownership shares are computed from each region's own capacities; the price change uses the national system cost per kWh with the region's ElCom reference price and surcharges (median of its municipalities); the import share stays national (import from abroad); transmission is 0;
- utility per region with the coefficients of its language region (draw by draw), aggregated with the population (BFS STATPOP) to DE-CH, FR-CH and national; TI has no coefficients in the choice model and is excluded in the main regional analysis (sensitivities with DE-CH, FR-CH and mixed coefficients);
- inputs (ElCom tariffs per municipality, LINDAS municipality register, STATPOP) are fetched by own rules for completed years only.

Figures of the regional main analysis (main text; rule `make_plots_regional`, `build/figures/{png,pdf,svg}/*_regional.*`): fig1 preference rank vs. cost rank (both on the 11 scenarios with a cost value), fig2 utility with 96 % HDI and fig3/figA1 attribute contributions (Switzerland, DE-CH, FR-CH; contributions = population-weighted mean of the regional z × β̃, totals in `build/data/regional/contributions_regional.csv`), fig4 ranks DE-CH vs. FR-CH, fig5 cost vs. choice share, fig6 P(rank 1) over a common shift Δ of all regional reference prices, fig7 a schematic tile map of the rank-1 scenario per region, fig8 the population share per rank-1 scenario. The national aggregate has the same figures with the suffix `_national` (appendix). All figures share the scenario order and colours of the section `figures` in `config/default.yaml` and state analysis, interval and price year in their caption.

Pairwise choice probabilities (as in Tröndle et al. 2025, Fig. 1–4; rules `pairwise_regional`, `plot_pairwise`, `choice_maps`, settings in the sections `pairwise` and `maps` of `config/default.yaml`): per posterior draw and region p = logistic(u_1 − u_2), aggregated as the population-weighted mean of the regional probabilities. fig9 is the matrix of all pairs (lower triangle, scenarios by cost), fig10 the maps per configured pair (expected value and both bounds of the credible interval per region; TI no data), each with the colour range 0–100 % and a narrowed variant (`maps.color_range_variant`, suffix `_range40-60`). Tables in `build/data/pairwise/`, including the deviation from the aggregation of the utilities (`aggregation_comparison_regional.csv`). The maps run in their own conda environment `envs/maps.yaml` (geopandas).

The import attribute is the net electricity import from abroad divided by the electricity consumption (annual sums). The switch `imports.definition` in `config/default.yaml` (default `electricity`) selects for the regional main analysis instead `electricity_fuels` (+ imports of natural gas, hydrogen and synthetic methane) or `electricity_fuels_diesel` (+ synthetic diesel); both fuel variants are always part of the regional sensitivity table (rule `import_shares`, `build/data/regional/import_shares_regional.csv`). Assumption: fuels are counted with their energy content, 1 GWh fuel = 1 GWh electricity.

Regional results are written to files with the suffix `_regional` (`build/data/utility_rankings_regional.csv`, `build/data/regional/`, `build/data/sensitivity/*_regional.csv`) and tested against the frozen references `data/processed/*_regional.csv` and `data/processed/regional_attributes.csv`.

The national aggregate (attributes computed for Switzerland as a whole, utility per language region; tables without suffix, figures with the suffix `_national`, and the reference-price sensitivity above) is always computed as a secondary analysis and keeps its own references. With `spatial.resolution: national` the rule `all` builds only the national aggregate (the regional outputs are still built for the tests).

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
