# test-project-josua

testing

This repository contains the entire scientific project, including code and report. The philosophy behind this repository is that no intermediary results are included, but all results are computed from raw data and code.

## Getting ready

You need [conda](https://conda.org) to run the analysis. Using conda, you can create an environment from within you can run it:

    conda env create -f environment.yaml --no-default-packages

## Run the analysis

    snakemake

This will run all analysis steps to reproduce results and eventually build the report.

You can also run certain parts only by using other `snakemake` rules; to get a list of all rules run `snakemake --list`.

To generate a PDF of the dependency graph of all steps `build/dag.pdf` run:

    snakemake dag


## Be notified of build successes or fails

As the execution of this workflow may take a while, you can be notified whenever the execution terminates either successfully or unsuccessfully. Notifications are sent by the webservice [Pushcut](https://pushcut.io/) for which you need a free account. To activate notifications, add your Pushcut secret to the configuration using the configuration key `pushcut_secret`. You can add the key to your configuration file, or you can run the workflow the following way to receive notifications:

    snakemake --config pushcut_secret=<your-secret>

This workflow will then trigger the Pushcut notifications `snakemake_succeeded` and `snakemake_failed`.

## Run the tests

    snakemake test

## Repo structure

* `report`: contains all files necessary to build the report; plots and result files are not in here but generated automatically
* `scripts`: contains the Python source code as scripts
* `rules`: contains Snakemake rule definitions
* `envs`: contains execution environments
* `tests`: contains the test code
* `config`: configurations used in the study
* `profiles`: Snakemake execution profiles
* `data`: place for raw data
* `build`: will contain all results (does not exist initially)

## License

The code in this repo is MIT licensed, see `./LICENSE.md`.
