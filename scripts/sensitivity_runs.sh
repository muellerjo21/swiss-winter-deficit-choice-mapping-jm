#!/bin/bash
# Named sensitivities of the regional main analysis for the weather years 2016-2018 (results in the paper,
# chapter 4). Each run overrides one setting with --config, rebuilds the regional analysis and copies its tables to
# docs/sensitivities/<year>/<name>/. At the end the main analysis is rebuilt without overrides, so build/ is in the
# default state again.
#
# Usage (project root, conda environment active or SNAKEMAKE pointing to its snakemake):
#   bash scripts/sensitivity_runs.sh [years...]        default: 2016 2017 2018
# Runtime: about 2-4 min per run (the choice model is read each time); 15 runs per year.
#
# Notes:
# - The variants "import: regional balance", "land: national share" and the Ticino variants are computed inside every
#   run (scripts/regional_utility.py) and are in sensitivity_regional.csv of the run "main".
# - The copies for 2016 in docs/sensitivities/2016 were made on 17 Nov 2026 with an earlier version of this script
#   that copied rank1_population_share_regional.csv instead of sensitivity_regional.csv; the 2016 variants of
#   sensitivity_regional.csv are in data/processed/sensitivity_regional.csv.
set -u
cd "$(dirname "$0")/.."
SNAKEMAKE=${SNAKEMAKE:-snakemake}
OUT=docs/sensitivities
T="build/data/utility_rankings_regional.csv build/data/regional/region_rankings_regional.csv build/data/regional/regional_attributes.csv build/data/regional/sensitivity_regional.csv build/data/regional/rank1_population_share_regional.csv"
YEARS=${*:-2016 2017 2018}

run() { y=$1; name=$2; shift 2
  $SNAKEMAKE --cores 1 --rerun-incomplete $T --config weather_year=$y "$@" > "$OUT/$y.$name.log" 2>&1
  rc=$?
  mkdir -p "$OUT/$y/$name"
  for f in $T; do cp -L "$f" "$OUT/$y/$name/"; done
  rm -f "$OUT/$y.$name.log"
  echo "$y $name exit $rc"; }

for y in $YEARS; do
  run $y main
  run $y scope_total 'price={"cost_scope": "total"}'
  run $y scope_electricity 'price={"cost_scope": "electricity"}'
  run $y scope_electricity_fuel 'price={"cost_scope": "electricity_fuel"}'
  run $y pref_minus20 'price={"energy_reference_ct_per_kwh": 13.552}'
  run $y pref_plus20 'price={"energy_reference_ct_per_kwh": 20.328}'
  run $y margin20 'price={"margin": 0.2}'
  run $y margin30 'price={"margin": 0.3}'
  run $y imp_electricity 'imports={"definition": "electricity"}'
  run $y imp_fuels 'imports={"definition": "electricity_fuels"}'
  run $y imp_denominator_elec 'imports={"denominator": "electricity"}'
  run $y tax_B 'price={"energy_surcharge": "by_carrier_2025"}'
  run $y tax_old 'price={"energy_surcharge": "electricity_only_2025", "energy_vat": 0}'
  run $y tax_A_noVAT 'price={"energy_vat": 0}'
  run $y model_jan2026 'data={"choice_model": "jan_2026"}'
done

# back to the default state
$SNAKEMAKE --cores 1 all > /dev/null 2>&1 && echo "main analysis restored"
