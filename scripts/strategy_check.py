"""Independent check (no pipeline code): does the content of each result file in data/raw match its label (Mellot et
al., Table 1, criteria as given by the user)? Swiss locations = all except AUT, DEU, FRA, ITA.
Measures per file:
- energy_cap (GW, dimension loc_techs) summed over the Swiss locations: alpine PV (alpine_pv_subsidised +
  alpine_pv_not_subsidised), wind (wind_onshore_*), rooftop PV (roof_mounted_pv), fossil gas turbines (ccgt_natgas,
  scgt_natgas), renewable-methane gas turbines (ccgt, scgt_renewable), DACCS (daccs_local);
- carrier_prod (GWh, summed over the 4-hour time steps and the Swiss locations): electricity from CHP (chp_methane,
  chp_biofuel, chp_waste), hydrogen imports (import_hydrogen), fossil natural gas imports (import_natgas),
  electricity from fossil and from renewable-methane gas turbines.
The scenario of a file is read from its name (barrier_<scenario>,...); EP2050+ of the same weather year
(barrier_baseline,..._no_self_sufficiency without fixed neighbours, or barrier_baseline_no_self_sufficiency for 2016)
is the reference for the relative criteria (Mellot et al., Table 1: Alpine PV up to 13.0 GW; wind about twice EP2050+, up
to 4.4 GW; rooftop PV about +20 % (7.5 GW); CHP production up to 2 x EP2050+; hydrogen imports > 0, up to 11.1 TWh/a;
S/CCGT (Fossil) + DACCS with fossil gas turbines and DACCS; S/CCGT (Ren. Methane) with renewable methane, hydrogen
imports only with H2; MIX / RE MIX combinations, RE MIX without fossil methane). The DACCS capacity has no unit in the
files and is only checked for > 0.
Not part of the Snakemake workflow (standalone check of the input data, documented in docs/data_provenance.md).
Usage (project root): python scripts/strategy_check.py docs/strategy_check.csv"""
import glob, re, sys
from pathlib import Path
import pandas as pd, xarray as xr

FOREIGN = {"AUT", "DEU", "FRA", "ITA"}


def measures(path):
    ds = xr.open_dataset(path)
    cap = ds["energy_cap"].to_series()
    cap = cap[[i.split("::")[0] not in FOREIGN for i in cap.index]]
    cap_tech = cap.groupby([i.split("::")[1] for i in cap.index]).sum()
    prod = ds["carrier_prod"].sum("timesteps").to_series()
    prod = prod[[i.split("::")[0] not in FOREIGN for i in prod.index]]
    prod_tc = prod.groupby([("::".join(i.split("::")[1:])) for i in prod.index]).sum()
    t = pd.DatetimeIndex(ds["timesteps"].values)
    ds.close()
    c = lambda *techs: float(sum(cap_tech.get(x, 0.0) for x in techs))
    p = lambda *keys: float(sum(prod_tc.get(k, 0.0) for k in keys)) / 1e3  # TWh
    return {"weather_year": int(pd.Series(t.year).mode()[0]),
            "alpine_pv_gw": c("alpine_pv_subsidised", "alpine_pv_not_subsidised"),
            "wind_gw": c("wind_onshore_monopoly", "wind_onshore_competing"),
            "roof_pv_gw": c("roof_mounted_pv"),
            "gas_turbines_fossil_gw": c("ccgt_natgas", "scgt_natgas"),
            "gas_turbines_renewable_gw": c("ccgt", "scgt_renewable"),
            "daccs_gw": c("daccs_local"),
            "chp_electricity_twh": p("chp_methane::electricity", "chp_biofuel::electricity", "chp_waste::electricity"),
            "h2_import_twh": p("import_hydrogen::hydrogen"),
            "natgas_import_twh": p("import_natgas::natural_gas"),
            "gas_turbines_fossil_twh": p("ccgt_natgas::electricity", "scgt_natgas::electricity"),
            "gas_turbines_renewable_twh": p("ccgt::electricity", "scgt_renewable::electricity")}


if __name__ == "__main__":
    rows = []
    for path in sorted(glob.glob("data/raw/20*/*.nc")):
        name = Path(path).name
        scenario = re.match(r"barrier_([a-z0-9_]+?)(,|_result)", name).group(1)
        if scenario == "baseline" and "no_self_sufficiency" in name:
            scenario = "ep2050" if "neighbours_fixed" not in name else "ep2050_neighbours_fixed"
        elif scenario == "baseline_no_self_sufficiency":
            scenario = "ep2050"
        rows.append({"folder": Path(path).parent.name, "file": name, "label": scenario, **measures(path)})
    pd.DataFrame(rows).to_csv(sys.argv[1], index=False)
    print(len(rows), "files")
