"""Independent check (no pipeline code): weather year of every Calliope result file from its content, compared with the
year in its file name / folder. Reference: Mellot et al., Supplement Table 1S, annual building heat demand 55.1 /
53.1 / 49.0 TWh and annual electricity demand (without heat pumps and electric vehicles) 56.9 / 56.9 / 56.3 TWh for
2016 / 2017 / 2018; time steps 2196 (leap year 2016) or 2190.
Content measures (Swiss locations = all except AUT, DEU, FRA, ITA; values in GWh, summed over the 4-hour blocks):
- heat: |carrier_con| of loc_tech_carriers "<loc>::demand_buildings_heat::<carrier>";
- electricity: |carrier_con| of "<loc>::demand_elec::electricity" (only the exogenous demand, without heat pumps and
  electric vehicles, which are separate technologies);
- number of time steps and the calendar year of the time step labels.
Year by content = the reference year with the smallest distance in heat and electricity (TWh), checked against the
number of time steps. For files with "barrier_baseline" in the name also the winter (Oct-Mar) net import over the
Swiss cross-border lines and the Swiss cost (see independent_check.py).
The year in the file name is the first 20xx that is not part of another token (so "EP2050" is not read as 2050).
Not part of the Snakemake workflow (standalone check of the input data, documented in docs/data_provenance.md).
Usage (project root): python scripts/weather_year_check.py docs/weather_year_check.csv"""
import glob, re, sys
from pathlib import Path
import numpy as np, pandas as pd, xarray as xr

FOREIGN = {"AUT", "DEU", "FRA", "ITA"}
REF = {2016: (55.1, 56.9, 2196), 2017: (53.1, 56.9, 2190), 2018: (49.0, 56.3, 2190)}


YEAR_IN_NAME = re.compile(r"(?<![A-Za-z0-9])(20\d\d)(?![0-9])")  # 2016 in "_2016_", not 2050 in "EP2050"


def entries(ds, dim):
    return pd.DataFrame([i.split("::") for i in ds[dim].values], columns=["loc", "tech", "carrier"])


if __name__ == "__main__":
    rows = []
    for path in sorted(glob.glob("data/raw/20*/*.nc") + glob.glob("data/check_files_josua/*.nc")):
        ds = xr.open_dataset(path)
        con, prod = entries(ds, "loc_tech_carriers_con"), entries(ds, "loc_tech_carriers_prod")
        swiss_con = ~con["loc"].isin(FOREIGN)
        total = lambda mask: float(np.abs(ds["carrier_con"].isel(loc_tech_carriers_con=np.where(mask)[0])).sum()) / 1e3
        heat = total(swiss_con & (con["tech"] == "demand_buildings_heat"))
        elec = total(swiss_con & (con["tech"] == "demand_elec") & (con["carrier"] == "electricity"))
        t = pd.DatetimeIndex(ds["timesteps"].values)
        dist = {y: abs(heat - h) + abs(elec - e) for y, (h, e, n) in REF.items()}
        year_content = min(dist, key=dist.get)
        name_year = YEAR_IN_NAME.search(Path(path).name)
        folder = Path(path).parent.name
        row = {"file": Path(path).name, "folder": folder,
               "year_name": int(name_year.group(1)) if name_year else None,
               "year_folder": int(folder) if folder.isdigit() else None,
               "heat_buildings_twh": heat, "electricity_demand_twh": elec, "n_timesteps": len(t),
               "label_year": int(pd.Series(t.year).mode()[0]), "year_content": year_content,
               "distance_twh": dist[year_content], "timesteps_match": len(t) == REF[year_content][2]}
        if "barrier_baseline" in Path(path).name:
            lines = lambda d: ((d["tech"].str.startswith("ac_transmission:")) & (d["carrier"] == "electricity")
                               & ~d["loc"].isin(FOREIGN) & d["tech"].str.split(":").str[1].isin(FOREIGN))
            imp = ds["carrier_prod"].isel(loc_tech_carriers_prod=np.where(lines(prod))[0]).sum("loc_tech_carriers_prod").values
            exp = np.abs(ds["carrier_con"].isel(loc_tech_carriers_con=np.where(lines(con))[0])).sum("loc_tech_carriers_con").values
            winter = np.asarray((t.month >= 10) | (t.month <= 3))
            cost = ds["cost"].sel(costs="monetary").to_series()
            row["winter_net_import_twh"] = (imp - exp)[winter].sum() / 1e3
            row["cost_swiss_meur"] = float(cost[[i.split("::")[0] not in FOREIGN for i in cost.index]].sum())
        rows.append(row)
        ds.close()
    pd.DataFrame(rows).to_csv(sys.argv[1], index=False)
    print(len(rows), "files")
