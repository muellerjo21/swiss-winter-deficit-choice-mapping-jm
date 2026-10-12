# Legacy: first approach (not maintained)

This folder documents the first, exploratory approach of the project. It is **not maintained** and
has been **replaced by the Snakemake pipeline** in the repository root (`Snakefile`, `scripts/`,
`src/`, `tests/`). It is kept only to document how the mapping was developed.

```
legacy/
├── legacy_config.py   # constants of the old 6-attribute approach (DATA_PATH, SCENARIOS_PATH, ...)
├── choice_model.py    # utility computation with the old published-paper model (6 attributes)
├── data/manual/       # manually transcribed Mellot et al. scenario values (scenarios.csv)
├── notebooks/         # exploratory notebooks 01-08
└── output/            # write target of the notebooks (instead of data/processed/ and graphics/)
```

- `notebooks/01` and `02` use the old model (`data/raw/choice-model-inference.nc`, see
  `legacy_config.DATA_PATH`). `notebooks/03`-`08` explore the scenario data and derive the
  attribute functions that the pipeline uses today (`src/load_data.py`).
- The notebooks import from `src/` (`sys.path.append("../../src")`) and, for `choice_model` /
  `legacy_config`, from this folder (`sys.path.append("..")`). They therefore only run from
  within `legacy/notebooks/`.
- **Do not execute the notebooks in place** if results matter: they call live APIs (ElCom,
  ECB EUR/CHF, Swissgrid) and write to `output/` (`08` additionally downloads into `data/raw/`).
  The frozen reference results in `data/processed/` and `graphics/` are produced only by the
  pipeline and must not be overwritten. To re-run a notebook, do it in a copy of the repository.
