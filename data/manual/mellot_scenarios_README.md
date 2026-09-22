# Data dictionary: mellot_scenarios.csv

Manually transcribed from Mellot et al. (2024), "Mitigating future winter
electricity deficits: A case study from Switzerland" (main text Tables 1 and 3)
and its Supplementary Material (Figure 1S). No output data exists on Zenodo
(zenodo.org/records/10887523) beyond the runnable model itself; these are the
only precise scenario-level numbers publicly available without running the
model ourselves.

## Known gaps (deliberately left blank, not guessed)

- `fuel_imports_twh`, `gross_winter_imports_twh`, `buildings_heat_electrification_pct` for **"EP2050+ (5TWh constraint)"**: Mellot et al. do not report these in Table 3 for this scenario (it only appears in Table 1's scenario definitions and the main text's cost figure).
- **Transmission capacity**: no column at all. Based on the Supplementary Material's Section 5.3 ("Electricity transmission and storage"), which describes only storage technologies (battery, pumped hydro, hydrogen) and no domestic transmission capacity, cost, or constraint parameters, intra-Switzerland transmission appears to be unconstrained ("copper-plate") in the model. Only cross-border transfer capacities (Switzerland <-> neighbours) are fixed inputs, taken from ENTSO-E projected grid data. This supports (but does not conclusively prove) the assumption of unchanged transmission capacity across scenarios used in the proposal's mapping table.

## Action item before relying on `land_use_km2_approx` for real analysis

Ask Tim/Adrien directly for the exact numeric values behind Figure 1S, rather than continuing to rely on a visual estimate. Suggested question: *"Do you have the exact land use values (in km²) per scenario behind Figure 1S, rather than just the chart?"*