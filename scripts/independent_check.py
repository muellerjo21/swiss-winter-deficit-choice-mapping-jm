"""Independent check of the Calliope result files (no pipeline code): per file the winter and annual net electricity
import of Switzerland over its cross-border lines and the total cost.

Data (Calliope 0.6 result files, NetCDF):
- carrier_prod / carrier_con (loc_tech_carriers_prod / _con x timesteps): energy produced / consumed per time step.
  Time steps: 4-hour blocks of one calendar year (2190 steps, timestep_resolution 4 h, timestep_weights 1), labelled by
  their start time (00:00, 04:00, ..., 20:00). Values are energy per block, so sums over blocks give energy.
- Unit: no unit attribute in the files; GWh is inferred from the electricity demand (demand_elec, Swiss locations,
  about 57'000 per year = 57 TWh, printed as a check).
- Locations: foreign = the four neighbours AUT, DEU, FRA, ITA (FR is the canton of Fribourg); all other locations are
  Swiss (23 regions).
- Cross-border lines: loc_tech_carriers "<Swiss location>::ac_transmission:<foreign location>::electricity".
  Import into Switzerland = carrier_prod of these entries (electricity delivered at the Swiss end), export =
  carrier_con of the same entries (electricity sent into the line at the Swiss end). Net import = import - export,
  measured at the Swiss end (as a check also at the foreign end: carrier_con - carrier_prod of
  "<foreign>::ac_transmission:<Swiss>::electricity"; the difference is the line losses).
- Winter half-year: 1 Oct 00:00 to 31 Dec 24:00 and 1 Jan 00:00 to 31 Mar 24:00 of the modelled calendar year, i.e. the
  time steps with start time in October-December or January-March. Blocks start at midnight, so none crosses the
  boundary (1 Apr 00:00 and 1 Oct 00:00 are block starts). The year is one calendar year, so the "winter" consists of
  January-March and October-December of the same weather year.
- Cost: variable cost (costs = monetary, loc_techs_cost): total over all locations, and over the Swiss locations
  (including the Swiss end of the cross-border lines). Unit: model currency, read as million EUR. Also the solver
  objective (attribute objective_function_value).
Not part of the Snakemake workflow (standalone check of the input data, documented in docs/data_provenance.md).
Usage (project root): python scripts/independent_check.py docs/independent_check.csv"""
import glob, sys
from pathlib import Path
import numpy as np, pandas as pd, xarray as xr

FOREIGN = {"AUT", "DEU", "FRA", "ITA"}


def split(index):
    return pd.DataFrame([i.split("::") for i in index], columns=["loc", "tech", "carrier"], index=index)


def check(path):
    ds = xr.open_dataset(path)
    t = pd.DatetimeIndex(ds["timesteps"].values)
    winter = np.asarray((t.month >= 10) | (t.month <= 3))
    prod, con = split(ds["loc_tech_carriers_prod"].values), split(ds["loc_tech_carriers_con"].values)
    is_line = lambda d, side: (d["tech"].str.startswith("ac_transmission:") & (d["carrier"] == "electricity")
                               & (d["loc"].isin(FOREIGN) if side == "foreign" else ~d["loc"].isin(FOREIGN))
                               & (d["tech"].str.split(":").str[1].isin(FOREIGN) if side == "swiss"
                                  else ~d["tech"].str.split(":").str[1].isin(FOREIGN)))
    sel = lambda var, d, mask: ds[var].sel({var.replace("carrier", "loc_tech_carriers"): d.index[mask].tolist()}).values
    imp = sel("carrier_prod", prod, is_line(prod, "swiss")).sum(0)
    exp = np.abs(sel("carrier_con", con, is_line(con, "swiss"))).sum(0)
    net = imp - exp
    f_out = np.abs(sel("carrier_con", con, is_line(con, "foreign"))).sum(0) - sel("carrier_prod", prod, is_line(prod, "foreign")).sum(0)
    demand = np.abs(sel("carrier_con", con, (con["tech"] == "demand_elec") & ~con["loc"].isin(FOREIGN))).sum()
    cost = ds["cost"].sel(costs="monetary").to_series()
    cost_loc = pd.Series([i.split("::")[0] for i in cost.index], index=cost.index)
    overrides = [o for o in ds.attrs.get("applied_overrides", "").split(";") if o]
    row = {"folder": str(Path(path).parent), "file": Path(path).name, "weather_year": int(pd.Series(t.year).mode()[0]),
           "n_timesteps": len(t), "resolution_h": float(np.unique(ds["timestep_resolution"].values)[0]),
           "scenario_attr": ds.attrs.get("scenario"), "time_finished": ds.attrs.get("time_finished"),
           "n_lines": int(is_line(prod, "swiss").sum()),
           "winter_net_import_twh": net[winter].sum() / 1e3, "annual_net_import_twh": net.sum() / 1e3,
           "winter_net_import_foreign_side_twh": f_out[winter].sum() / 1e3,
           "winter_import_twh": imp[winter].sum() / 1e3, "winter_export_twh": exp[winter].sum() / 1e3,
           "demand_elec_twh": demand / 1e3,
           "cost_total_all_locations": float(cost.sum()), "cost_swiss_locations": float(cost[~cost_loc.isin(FOREIGN)].sum()),
           "objective": float(ds.attrs.get("objective_function_value", np.nan)),
           "only_winter_constraint": "only_winter_constraint" in overrides,
           "neighbours_fixed": any(o.startswith("ep2050_baseline_neighbours") for o in overrides),
           "weather_override": next((o for o in overrides if o.startswith("year20")), ""),
           "n_overrides": len(overrides), "overrides": ";".join(sorted(overrides))}
    ds.close()
    return row


if __name__ == "__main__":
    files = sorted(glob.glob("data/raw/20*/*.nc") + glob.glob("data/check_files_josua/*.nc"))
    pd.DataFrame([check(f) for f in files]).to_csv(sys.argv[1], index=False)
    print(len(files), "files")
