# Provenance of input data that are not downloaded by the workflow

Large input files are not committed (`data/raw/` is git-ignored). This file records where they come from and how to
check that a local copy is the right one.

## Choice model "measured_2026_languages" (corrected model, main model since 21 Nov 2026)

| | |
|---|---|
| Sender | Tim Tröndle (supervisor); corrected model of the cleaned choice data, replacing the faulty model of "measured" below |
| Received | 21 Nov 2026 |
| File | `data/raw/measured.nc`, NetCDF-4 (ArviZ InferenceData), created 20 Nov 2026 15:11 UTC (PyMC 6.4.0) |
| Size, SHA-256 | 8'274'292'636 bytes, `eeaf4286d2f0ed92f2a89b218fb58d6f81f5857adb6a2396391745ed51e605a7` |

Structure: 4 chains x 1000 draws; 11 attributes; European mean `beta_partworths` (= `alpha`) and an effect per language
group `effect_country` (= `z_country` x `sigma_country`) for 10 groups: DA, DE, DE-CH, EN, FR, FR-CH, PL, PT, RO, SV.
No group for Switzerland as a whole and none for Italian-speaking Switzerland (TI gets the coefficients of
`spatial.regional.ticino`). 7'574 respondents and 60'592 choice situations, the same respondents, situations,
attribute values and choices as "measured"; Switzerland: DE-CH 546 respondents (4'368 situations), FR-CH 337
(2'696). No `mobile_partworths`. Attribute scaling as before (import 0.9, land 0.08, transmission 2.0, others 1.0).
Checked: u_left = x_left_scaled (alpha + effect) + left_intercept (respondent), u_right without intercept, p_left =
logistic(u_left - u_right), reproduced to 9e-16. Config entry: `data.choice_models.measured_2026_languages`.

## Choice model "measured" (cleaned choice data, November 2026; option measured_2026, superseded)

| | |
|---|---|
| Sender | Kristiina Joon, Climate Policy Lab (ETH Zürich) |
| Received | 17 Nov 2026, 07:41 UTC, download from a polybox.ethz.ch public share (link not recorded here; it contains an access token) |
| Delivered file | `measured.nc.cpgz`: gzip-compressed cpio archive (odc format, macOS Archive Utility), gzip timestamp 11 Nov 2026 14:25:43 |
| Size, SHA-256 of the delivered file | 7'820'296'306 bytes, `a3b64b8fe6cab11158745341a458b588ba4c340319d81dc1d1d047ad6a353119` |
| Content | one file `measured.nc`, NetCDF-4 (HDF5), modification time in the archive 31 Jul 2026 |
| Size, SHA-256 of `measured.nc` | 7'821'881'176 bytes, `ae75fb944fb85ffcdb9421349f571c930eb6fb6785e2acc760e5a3ce6dc909fb` |
| Location used by the workflow | `data/raw/choice-model-measured/measured.nc` |

Unpack into a new, empty folder:

    mkdir data/raw/choice-model-measured
    cd data/raw/choice-model-measured && gzip -dc ../measured.nc.cpgz | cpio -id
    shasum -a 256 measured.nc

Structure (ArviZ InferenceData, groups posterior, posterior_predictive, sample_stats, observed_data, constant_data):
4 chains x 1000 draws; 11 attributes; 9 countries (Denmark, France, Germany, Ireland, Poland, Portugal, Romania,
Sweden, Switzerland); 7'574 respondents (883 in Switzerland), 60'592 choice situations. Partworths: European mean
`beta_partworths` (= `alpha`) and country effect `effect_country` (= `z_country` x `sigma_country`); the coefficients
of a country are `beta_partworths + effect_country[country]`. No language split within Switzerland and no
`mobile_partworths` / `m`. Attribute scaling (raw / scaled survey values) as in the January 2026 model: import 0.9,
land 0.08, transmission 2.0, all others 1.0.

## Choice model "jan_2026" (previous model)

`data/raw/choice-model-jan-2026.nc`: 10 language groups (DA, DE, DE-CH, EN, FR, FR-CH, PL, PT, SO, SV), 6'934
respondents (DE-CH 385, FR-CH 388), `beta_partworths` per group (= `alpha + effect_country`), plus `mobile_partworths`
and the respondent flag `m`. Provided by the authors; the published model of Tröndle, Mey & Lilliestam (2025) is on
Zenodo, DOI 10.5281/zenodo.14501018.

## Calliope baseline control files (Mellot et al., November 2026)

| | |
|---|---|
| Source | Zenodo Sandbox, Record 606988, Version v1, Preview, unveröffentlicht, erhalten von Adrien Mellot am 17.11.2026 (test DOI, not citable) |
| Delivered as | `check_files_josua.zip`; available here only unpacked (folder `data/check_files_josua/`, no `._` macOS files), so the SHA-256 of the zip itself could not be recorded |
| Purpose | check of the baseline labelling (5 TWh winter import limit vs. EP2050+ with 9 TWh) |

| File | Size (bytes) | SHA-256 |
|---|---|---|
| `barrier_baseline,neighbours_fixed_by_EP2050_baseline_2016_result_4H.nc` | 82'837'389 | `d999d7d0247c1e263a97d0fa1b0146ea00272f8d60988dec26fc3e86af0f4319` |
| `barrier_baseline_no_self_sufficiency_result_4H.nc` | 77'485'594 | `96b6bba30c5fb4785beab6eae02430f9de23db44305be1fe7f3792d1f555f16d` |
| `barrier_baseline,sensitivity_weather_2017,neighbours_fixed_by_EP2050_baseline_2017_no_self_sufficiency_result_4H.nc` | 83'149'574 | `c3a541afc7c82f46a9137572448df4ee8ee194c51eb12e6fb6f5fb9adc78de0c` |
| `barrier_baseline,sensitivity_weather_2017_no_self_sufficiency_result_4H.nc` | 84'348'682 | `6dc5c8a4d3c3192fa25908a87a43cd684c7052c36a2e837c72b4887baca2ffbe` |
| `barrier_baseline,sensitivity_weather_2018,neighbours_fixed_by_EP2050_baseline_2018_no_self_sufficiency_result_4H.nc` | 81'549'995 | `3dd4be5add82ffd0ee06c5c85e4447e067d4de593a45c49a82c4b672e87b3c80` |
| `barrier_baseline,sensitivity_weather_2018_no_self_sufficiency_result_4H.nc` | 85'196'434 | `07a8e7fc3ddec7112ea885929469062e950b73da2a70181bec76bfff31a3a964` |

The two 2016 files differ from the 2016 files used by the workflow (`data/raw/2016/`, solved on 29 Jul 2024; the
control files were solved in November 2023). The 2017 and 2018 files with fixed neighbours and the 2018 file without
are identical to the files in `data/raw/`; the 2017 file without fixed neighbours is new.

Use in the workflow (17 Nov 2026): `barrier_baseline,sensitivity_weather_2017_no_self_sufficiency_result_4H.nc`
(SHA-256 `6dc5c8a4d3c3192fa25908a87a43cd684c7052c36a2e837c72b4887baca2ffbe`, source: Zenodo Sandbox preview, control
files of Adrien Mellot) is copied to `data/raw/2017/` and used as EP2050+ 2017. By content (winter net import
October-March: 5.0 TWh only in the 2016 baseline, 9.0 TWh in all `_no_self_sufficiency` files), the files used so
far as Baseline (5 TWh) 2017 and 2018 are EP2050+ runs with fixed neighbours; Baseline (5 TWh) exists for 2016 only.
The 2016 files stay the raw versions of July 2024; they are the versions in the record (MD5, see below).

## Checks of the Calliope result files (17 Nov 2026)

Three standalone scripts (no pipeline code; `xarray`, `pandas`, `numpy` only) check all 36 result files in
`data/raw/2016|2017|2018/` (the first two also the six control files in `data/check_files_josua/`). Results:
`docs/independent_check.csv`, `docs/weather_year_check.csv` and `docs/strategy_check.csv`.

    python scripts/independent_check.py docs/independent_check.csv
    python scripts/weather_year_check.py docs/weather_year_check.csv
    python scripts/strategy_check.py docs/strategy_check.csv

Method:
- Variables: `carrier_prod` and `carrier_con` (`loc_tech_carriers_prod` / `_con` x `timesteps`, energy per time step,
  GWh: the electricity demand `demand_elec` sums to 56.3-56.9 thousand per year), `cost` (`costs = monetary`,
  `loc_techs_cost`, read as million EUR), attributes `scenario`, `applied_overrides`, `time_finished`.
- Time steps: 4-hour blocks of one calendar year (2196 in 2016, otherwise 2190; `timestep_resolution` 4 h,
  `timestep_weights` 1), labelled by their start time.
- Winter half-year: blocks starting in January-March or October-December of the modelled year (1 Jan to 31 Mar and
  1 Oct to 31 Dec; all blocks start at midnight, none crosses the boundary).
- Cross-border lines: the ten entries `<Swiss location>::ac_transmission:<AUT|DEU|FRA|ITA>::electricity`
  (`FR` is the canton of Fribourg, `FRA` France). Net import = `carrier_prod` - |`carrier_con`| at the Swiss end;
  measured at the foreign end it differs by up to 0.97 TWh (line losses), and only the Swiss end hits 5.0 / 9.0 TWh
  exactly.
- Cost: sum of `cost` over the Swiss locations (including the Swiss end of the cross-border lines) and over all
  locations.
- Weather year from the content: annual building heat demand (`demand_buildings_heat`) and electricity demand
  (`demand_elec`, without heat pumps and electric vehicles) at the Swiss locations and the number of time steps,
  compared with Mellot et al., Supplement Table 1S (heat 55.1 / 53.1 / 49.0 TWh, electricity 56.9 / 56.9 / 56.3 TWh
  for 2016 / 2017 / 2018); the year in the file name is a standalone 20xx (not the 2050 of "EP2050").
- Strategy content against the label: installed capacities `energy_cap` (GW, Swiss locations) of alpine PV
  (`alpine_pv_subsidised`, `alpine_pv_not_subsidised`), wind (`wind_onshore_*`), rooftop PV (`roof_mounted_pv`), fossil
  gas turbines (`ccgt_natgas`, `scgt_natgas`), renewable-methane gas turbines (`ccgt`, `scgt_renewable`) and DACCS
  (`daccs_local`, no unit in the files, checked for > 0), and annual `carrier_prod` (TWh) of CHP electricity
  (`chp_methane`, `chp_biofuel`, `chp_waste`), hydrogen imports (`import_hydrogen`) and fossil gas imports
  (`import_natgas`), compared with the definitions in Mellot et al., Table 1 and with EP2050+ of the same weather year
  (EP2050+: 0 GW alpine PV, 2.22 GW wind, 37.51 GW rooftop PV, no gas turbines, no hydrogen imports).

Results:
- All 30 strategy files have a winter net import of exactly 5.0 TWh; all files ending in `_no_self_sufficiency` (and
  the 2016 file `barrier_baseline_no_self_sufficiency_result_4H.nc`) exactly 9.0 TWh, i.e. EP2050+. Baseline (5 TWh)
  exists for 2016 only. The files used as Baseline (5 TWh) 2017 and 2018 until 17 Nov 2026 were EP2050+ runs with
  fixed neighbours: a mapping error of this workflow (the limit is stored neither in the overrides nor in the
  scenario name, which never contains "no_self_sufficiency"); corrected in `config/default.yaml`.
- The weather year from the content matches the year in the file name / folder for all files (heat and electricity
  within 0.06 TWh of Table 1S, time steps as expected).
- MD5 of all 36 files in `data/raw/` = the file list of the Zenodo Sandbox record 606988 (v1 preview), including the
  2016 Baseline (5 TWh) of July 2024 used here; the two 2016 control files (November 2023) are older runs that are not
  in the record.
- The content of all 36 files matches their label (Table 1): Alpine PV 7.7-10.4 GW alpine PV; Wind 4.45 GW = 2.00 x
  EP2050+; Roof PV++ +7.4 to +7.5 GW rooftop PV (+20 %); H2 Imports 2.0-11.1 TWh hydrogen imports; S/CCGT (Fossil) +
  DACCS fossil gas turbines, fossil gas imports and DACCS; S/CCGT (Ren. Methane) with and without H2 renewable-methane
  gas turbines without fossil gas; MIX with fossil gas, RE MIX without; no file looks like another strategy.
- S/CCGT (Ren. Methane) and S/CCGT (Ren. Methane) + H2 give practically identical results in every weather year
  (Swiss cost within 3 ppm, same winter import, attributes within 3e-4, utility within 1e-5), because the + H2 variant
  never uses hydrogen imports (0 TWh in all years; capacities and flows as without H2), as in Mellot et al., Table 3
  (both -3.6 %).
- CHP: the CHP scenario produces 10.28 TWh of CHP electricity in 2016 (2 x EP2050+ 2016) and 2017 and 8.35 TWh in
  2018, i.e. 3.2 x and 3.1 x EP2050+ of the same weather year. Consistent with a cap at 2 x EP2050+ 2016 (10.28 TWh) in
  every weather year (inferred from the results; the cap is not stored in the files).
- Scenarios per weather year: 12 (2016), 11 (2017), 11 (2018); common to all three years: 11 (all except
  Baseline 5 TWh).
