#!/bin/bash
# Named sensitivities of the regional main analysis for the weather years 2016-2018 (results in the paper,
# chapter 4). Each run overrides one setting with --config, rebuilds the regional analysis and copies its tables to
# docs/sensitivities/<year>/<name>/. At the end the main analysis is rebuilt without overrides, so build/ is in the
# default state again.
#
# Usage (project root, conda environment active or SNAKEMAKE pointing to its snakemake):
#   bash scripts/sensitivity_runs.sh [years...]        default: 2016 2017 2018
# Optional environment variables: OUT (output folder, default docs/sensitivities), VARIANTS (space-separated subset
# of the variant names below, default all).
# Runtime: about 1 min per run; 16 runs per year.
#
# Notes:
# - The variants "import: regional balance", "land: national share" and the Ticino variants are computed inside every
#   run (scripts/regional_utility.py) and are in sensitivity_regional.csv of the run "main".
# - The reference-price variants are p_ref -20 % and +20 % of price.energy_reference_ct_per_kwh (rounded to 10
#   significant digits, e.g. 13.552 and 20.328 for p_ref = 16.94).
# - All years were recomputed on 21 Nov 2026 with the choice model measured_2026_languages.
# - The restore at the end includes the regression tests; it reports no "main analysis restored" while the frozen
#   references (data/processed) belong to another configuration, e.g. after a change of the choice model.
set -u
cd "$(dirname "$0")/.."
SNAKEMAKE=${SNAKEMAKE:-snakemake}
OUT=${OUT:-docs/sensitivities}
VARIANTS=${VARIANTS:-}
T="build/data/utility_rankings_regional.csv build/data/regional/region_rankings_regional.csv build/data/regional/regional_attributes.csv build/data/regional/sensitivity_regional.csv build/data/regional/rank1_population_share_regional.csv"
YEARS=${*:-2016 2017 2018}

# Reference price of the main analysis and the variants p_ref x factor
PREF=$(awk '/^ *energy_reference_ct_per_kwh:/ {print $2; exit}' config/default.yaml)
pref() { awk -v p="$PREF" -v f="$1" 'BEGIN { printf "%.10g", p * f }'; }

run() { y=$1; name=$2; shift 2
  if [ -n "$VARIANTS" ] && [[ " $VARIANTS " != *" $name "* ]]; then return; fi
  mkdir -p "$OUT/$y/$name"
  $SNAKEMAKE --cores 1 --rerun-incomplete $T --config weather_year=$y "$@" > "$OUT/$y.$name.log" 2>&1
  rc=$?
  for f in $T; do cp -L "$f" "$OUT/$y/$name/"; done
  rm -f "$OUT/$y.$name.log"
  echo "$y $name exit $rc"; }

for y in $YEARS; do
  run $y main
  run $y scope_total 'price={"cost_scope": "total"}'
  run $y scope_electricity 'price={"cost_scope": "electricity"}'
  run $y scope_electricity_fuel 'price={"cost_scope": "electricity_fuel"}'
  run $y pref_minus20 "price={\"energy_reference_ct_per_kwh\": $(pref 0.8)}"
  run $y pref_plus20 "price={\"energy_reference_ct_per_kwh\": $(pref 1.2)}"
  run $y margin20 'price={"margin": 0.2}'
  run $y margin30 'price={"margin": 0.3}'
  run $y imp_electricity 'imports={"definition": "electricity"}'
  run $y imp_fuels 'imports={"definition": "electricity_fuels"}'
  run $y imp_denominator_elec 'imports={"denominator": "electricity"}'
  run $y tax_B 'price={"energy_surcharge": "by_carrier_2025"}'
  run $y tax_old 'price={"energy_surcharge": "electricity_only_2025", "energy_vat": 0}'
  run $y tax_A_noVAT 'price={"energy_vat": 0}'
  run $y model_jan2026 'data={"choice_model": "jan_2026"}'
  run $y model_measured_2026 'data={"choice_model": "measured_2026"}'
done

# back to the default state
$SNAKEMAKE --cores 1 all pipeline_map > /dev/null 2>&1 && echo "main analysis restored"
