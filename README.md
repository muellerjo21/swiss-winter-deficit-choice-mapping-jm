# Predicting Citizen Preferences for Switzerland's Winter Electricity Deficit Mitigation Scenarios Using a Discrete Choice Model

Semester project mapping winter-gap mitigation energy scenarios from Mellot et al. (2024), *"Mitigating future winter electricity deficits: A case study from Switzerland"*, onto the discrete choice model from Tröndle, Mey & Lilliestam (2025), *"Socially preferable and technically feasible: European citizens choose solar power and import independence over lower costs"*, to predict Swiss citizen preferences.

**Author:** Josua Müller
**Supervision:** Dr. Tim Tröndle, Prof. Anthony Patt

## Overview

The project applies an existing discrete choice model (Tröndle, Mey & Lilliestam 2025), fitted on European stated-preference data, to Switzerland. The model's attributes (technology shares, land use, transmission, import share, household energy cost change, ownership) are computed from the Calliope results of Mellot et al.'s (2024) twelve winter-deficit scenarios, which are then ranked by predicted utility and compared with Mellot et al.'s cost ranking.

- **Main analysis:** regional, on the 23 Calliope regions (20 cantons, AI_AR, BL_BS, NW_OW, TI), with the coefficients of the corrected choice model (`measured_2026_languages`: European mean + effect of the language group; DE-CH regions with DE-CH, FR-CH regions with FR-CH, TI with DE-CH) and population weights; 96 % HDI; weather year 2016. DE-CH and FR-CH are reported as groups of regions (canton language).
- **Cost attribute:** change of the energy price per kWh of final energy (electricity, heat, transport) against today's average energy price, `price.cost_scope: energy`: p_sim = (C / final energy · EUR/CHF · 100 · (1 + margin) + taxes and levies) · (1 + VAT), p_ref = BFE GEST 2025 consumer expenditure / final energy.
- **Import attribute:** electricity + fuel imports over final energy (`imports.definition: electricity_fuels_diesel`, `imports.denominator: final_energy`).
- **Secondary analyses:** national aggregate (appendix), weather years 2016–2018, sensitivities (reference price, cost factor, Ticino, land, import definition, taxes and levies, margin).

## Reproduce everything with one command

1. **Software.** Install [conda](https://conda.org) and create the workflow environment once:

       conda env create -f environment.yaml --no-default-packages
       conda activate swiss-winter-deficit

   If a Python virtual environment (e.g. `.venv`) is active, run `deactivate` first: its `python` would shadow the rules' conda environments.

2. **Input data** (git-ignored, not downloaded by the workflow), in `data/raw/`:

   | File | Content | Source |
   |---|---|---|
   | `data/raw/<year>/<file>.nc` for 2016, 2017, 2018 | Calliope results of Mellot et al., one file per scenario and weather year; the file names per year are listed in `scenarios` in `config/default.yaml` (`null` = no run); EP2050+ 2017 comes from Mellot's control files (`docs/data_provenance.md`) | record "Swiss-Calliope scenario results data" by A. Mellot (Zenodo, not yet published; preview access from the authors) |
   | `data/raw/choice-model-measured/measured.nc` | posterior of the choice model with the cleaned choice data (November 2026), unpacked from `measured.nc.cpgz` | Kristiina Joon, Climate Policy Lab; sender, date, sizes and SHA-256 in `docs/data_provenance.md` |
   | `data/raw/choice-model-jan-2026.nc` | previous choice model (January 2026), for comparison | provided by the authors; published model: Zenodo, DOI 10.5281/zenodo.14501018 |
   | `data/raw/flache_der_schweiz_nach_kantonen_in_quadratkilometern.csv` | canton areas, `data.canton_area` | Statista |

   Everything else is fetched by the workflow, for completed years only: ElCom tariffs and the municipality register (LINDAS), BFS STATPOP, the annual EUR/CHF rate (Frankfurter API), and swisstopo swissBOUNDARIES3D (release 2025-01, SHA-256 checked).

3. **Run** the whole analysis, all figures, the regression tests and the interactive pipeline map:

       snakemake all pipeline_map

   The profile `profiles/default` sets conda environments per rule (`envs/`) and one core. A full run takes about 2.5 minutes on one core (149 s measured on 20 Nov 2026; each Calliope result file is read once per rule). Results go to `build/`: tables in `build/data/`, figures in `build/figures/{png,pdf,svg}/`, logs in `build/logs/`, the test report in `build/test-report.html` and the map in `build/pipeline_map.html` (open it in a browser). Two consecutive runs give byte-identical results, including the SVG figures and the pipeline map (checked on 20 Nov 2026). On this machine `build` is a symlink to `build.nosync/`, which iCloud does not sync (git-ignored); in a fresh clone `build/` is an ordinary folder.

   The modules in `src/` are inputs of the rules that import them: a change of the code re-runs these rules. The download rules (`fetch_*`) are deliberately excluded, so that a code change does not repeat a download; re-fetch on purpose with `snakemake --forcerun <rule>`.

Other useful commands: `snakemake --list`, `snakemake dag` (rule graph as `build/dag.pdf`), `snakemake clean` (removes `build/`).

## Configuration

`config/default.yaml` is the only place for parameters; every value has its source in a comment and the code has no defaults of its own (a missing key stops with an error that names it). Switches can be changed there or for one run with `--config`, e.g. `snakemake all --config 'price={"energy_surcharge": "by_carrier_2025"}'`. The scripts get the values through the rules' params and through `src/config.py`, which reads the configuration of the run including its `--config` overrides (the Snakefile passes it in the environment variable `SWISS_WINTER_DEFICIT_CONFIG`). Besides the switches below, the file holds the conventions of the Calliope result files (`calliope`), the regions and their languages (`regions`), the mapping of the results to the choice-model attributes (`attributes`; every electricity-producing technology must be mapped or explicitly excluded, `src/checks.py`), the cost changes of Mellot et al., Table 3 (`mellot_cost_change_pct`), the scenario names of the figures (`figures.display_names`) and the download endpoints (`sources`).

| Key | Main analysis | Alternatives |
|---|---|---|
| `data.choice_model` | `measured_2026_languages` (corrected model, Nov 2026; language groups DE-CH / FR-CH) | `measured_2026` (faulty previous model, one coefficient set for Switzerland), `jan_2026` (model of January 2026, partworths per language group, with mobile shift) |
| `price.cost_scope` | `energy` (system cost / final energy, p_ref `energy_reference_ct_per_kwh` = 16.94 Rp./kWh) | `total`, `electricity`, `electricity_fuel` (electricity price variants with the ElCom reference price) |
| `price.energy_surcharge` | `constant_2025`: today's taxes and levies over today's energy mix, 7.74 Rp./kWh | `by_carrier_2025` (today's rate per end-use carrier, per scenario), `electricity_only_2025` (4.88, previous estimate) |
| `price.energy_vat` | 0.081 (MWSTG Art. 25) | `0` |
| `price.margin` | 0.10 | e.g. 0.2, 0.3 |
| `utility.mobile_share` | 0 | 0..1, **only meaningful with `jan_2026`** (the measured model has no mobile shift; the workflow stops otherwise) |
| `imports.definition` / `imports.denominator` | `electricity_fuels_diesel` / `final_energy` | `electricity`, `electricity_fuels` / `electricity` |
| `spatial.regional.ticino` | `de` | `fr`, `mixed`, `exclude`; with `measured_2026` (one Swiss coefficient set) `de`, `fr` and `mixed` give identical results (tested), only `exclude` differs |
| `weather_year` | 2016 | 2017, 2018 (all three are always compared, rule `weather_year_rankings`) |
| `spatial.resolution` | `regional` | `national` (only the national aggregate in rule `all`) |

`--config` passes nested numbers as text; the Snakefile turns them back into numbers (`rules/common.smk`, `numbers_from_text`).

## Outputs and tests

- Regional main analysis: `build/data/utility_rankings_regional.csv`, `build/data/regional/` (attributes, region rankings, population share with rank 1, sensitivities), figures `*_regional.*` (fig1–fig10). fig12 (`fig12_language_map`, figure only): majority main language per canton (BFS structural survey 2024) with the language border of the BFS language areas, next to the coefficient group (DE-CH, FR-CH) of each region; sources in `docs/data_provenance.md`.
- Weather years: `build/data/weather/` and fig11. EP2050+ (5 TWh constraint) exists for 2016 only: Mellot et al. have no 5 TWh runs for 2017 and 2018, also not in the new record. The files used as EP2050+ (5 TWh constraint) for 2017/2018 until 17 Nov 2026 end in `_no_self_sufficiency` and are EP2050+ with 9 TWh winter import: a mapping error of this workflow, corrected. The record contains the 2016 files of July 2024 used here. 12 scenarios in 2016, 11 in 2017 and 2018; 11 scenarios (all except EP2050+ (5 TWh constraint)) are common to all three years. S/CCGT (Ren. Methane) and S/CCGT (Ren. Methane) + H2 give practically identical results in every year because the + H2 variant never uses hydrogen imports, as in Mellot et al., Table 3. The CHP scenario is capped at 2 × the CHP production of EP2050+ 2016 (10.28 TWh) also in 2017 and 2018, i.e. about 3 × EP2050+ of these weather years (inferred from the results).
- Checks of the input files (standalone, not part of the workflow): `scripts/independent_check.py` (winter and annual net import, cost per file), `scripts/weather_year_check.py` (weather year from the content, Mellot et al. Table 1S) and `scripts/strategy_check.py` (strategy content against Mellot et al. Table 1); results in `docs/independent_check.csv`, `docs/weather_year_check.csv` and `docs/strategy_check.csv`, method in `docs/data_provenance.md`.
- Numbers of the paper that are not workflow outputs (run from the project root after `snakemake all`):
  - Named sensitivities for 2016-2018 (tax B, without VAT, previous surcharge 4.88, p_ref ±20 %, margin 20/30 %, cost scopes, import definitions, choice models jan_2026 and measured_2026): `SNAKEMAKE=<path to snakemake> bash scripts/sensitivity_runs.sh [years]` writes `docs/sensitivities/<year>/<variant>/` and rebuilds the main analysis at the end (about 1 min per run, 15 runs per year). The reference-price variants are derived from `price.energy_reference_ct_per_kwh` (±20 %). Optional: `OUT=<folder>` writes elsewhere, `VARIANTS="<names>"` runs a subset. All years were recomputed on 21 Nov 2026 with the main model `measured_2026_languages`; the variants `model_measured_2026` and `model_jan2026` give the results of the previous models.
  - Summary per year and variant (rank 1 national, DE-CH, FR-CH, P(rank 1), utility gap rank 1 - rank 2, including the in-run variants "import: regional balance" and "land: national share"): `python scripts/sensitivity_summary.py docs/sensitivity_summary.csv`.
  - Neighbouring ranks per weather year (utility difference, P(A > B), P(A chosen over B)) and the groups of tied ranks (neighbours with P(A > B) below `report.tie_threshold` = 0.95 or a utility difference below `report.tie_utility_tolerance`, a convention of this project): `python scripts/adjacent_pairs.py build/data docs/adjacent_pairs.csv docs/tie_groups.csv` with the Python of the workflow's conda environment.
- National aggregate (appendix): tables without suffix, figures `*_national.*`, reference-price sensitivity with real base years (fig6 national). Since 20 Nov 2026 its import attribute follows the definition of the main analysis (`imports.definition`, `imports.denominator`); before, it was the net electricity import over the electricity consumption.
- Previous configuration: `snakemake all --config 'data={"choice_model": "jan_2026"}' 'price={"energy_surcharge": "electricity_only_2025", "energy_vat": 0}'` computes the analysis with the previous model and taxes (the references frozen on 8 Nov 2026 are in the git history; later corrections, e.g. of the gas turbine mapping, change them slightly).
- The rule `test` compares `build/` with the frozen references in `data/processed/` (including `data/processed/weather/`) and `graphics/` (fig6 national) and checks the consistency of the results. The tests get their data from the workflow (fixtures in `tests/test_runner.py`), so they run through `snakemake all` or `snakemake test`, not with a plain `pytest`. After a deliberate change of the method, the references are refrozen by copying the new results there.

## Repository structure

```
.
├── Snakefile          # workflow definition
├── rules/             # helper functions of the Snakefile (common.smk)
├── config/            # all parameters (default.yaml)
├── envs/              # conda environments per rule
├── profiles/          # Snakemake execution profile (conda, 1 core)
├── scripts/           # thin Snakemake wrappers around src/
├── src/               # library code (attributes, price, utility, regional analysis, figures, maps)
├── tests/             # regression and consistency tests
├── docs/              # data provenance, checks, sensitivities, texts and template of the pipeline map
├── data/
│   ├── raw/           # input data (git-ignored)
│   └── processed/     # frozen, validated reference results
├── graphics/          # frozen reference figure (fig6 national)
└── build/             # workflow results (git-ignored)
```

**Licence of the boundaries.** swissBOUNDARIES3D is free geodata of swisstopo (open government data); use is free with source attribution "© swisstopo" (https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices). The figures credit swisstopo in their footnote.

## Status

Work in progress (code freeze in preparation).
