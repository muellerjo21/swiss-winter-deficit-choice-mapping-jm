"""Summary of the named sensitivities (docs/sensitivities, written by scripts/sensitivity_runs.sh) and of the
variants computed inside every run (sensitivity_regional.csv: "import: regional balance", "land: national share",
Ticino variants). One row per weather year x variant: rank 1 in Switzerland (national), DE-CH and FR-CH with
P(rank 1), rank 2 and the utility difference rank 1 - rank 2 (posterior means, national), and whether rank 1 of
DE-CH or FR-CH differs from the national rank 1.
In-run variants: the file sensitivity_regional.csv of the run "main" of each weather year (not the frozen test
reference in data/processed, which can lag behind the current choice model until it is refrozen).
Usage (project root): python scripts/sensitivity_summary.py docs/sensitivity_summary.csv"""
import glob, os, sys
import pandas as pd

sys.path.insert(0, "src")
from config import GROUP_TAGS as GROUPS, setting  # noqa: E402  (national, DE_CH, FR_CH)


def summarise(u: pd.DataFrame) -> dict:
    row = {}
    for g in GROUPS:
        s = u.sort_values(f"rank_{g}")
        row[f"rank1_{g}"] = s.iloc[0]["scenario_id"]
        row[f"p_rank1_{g}"] = s.iloc[0][f"p_rank1_{g}"]
    s = u.sort_values("rank_national")
    row["rank2_national"] = s.iloc[1]["scenario_id"]
    row["utility_gap_1_2_national"] = s.iloc[0]["utility_national"] - s.iloc[1]["utility_national"]
    row["regional_rank1_differs"] = (row["rank1_DE_CH"] != row["rank1_national"]) or (row["rank1_FR_CH"] != row["rank1_national"])
    return row


rows = []
for path in sorted(glob.glob("docs/sensitivities/20*/*/utility_rankings_regional.csv")):
    year, name = path.split(os.sep)[-3:-1]
    rows.append({"weather_year": int(year), "variant": name, "source": path, **summarise(pd.read_csv(path))})
in_run = {y: f"docs/sensitivities/{y}/main/sensitivity_regional.csv" for y in setting("sensitivity", "weather_years")}
for year, path in in_run.items():
    if not os.path.exists(path):
        continue
    for variant, u in pd.read_csv(path).groupby("variant", sort=False):
        if variant == "main" or variant.startswith("import: electricity"):
            continue                                   # main and import definitions are separate runs above
        rows.append({"weather_year": year, "variant": variant, "source": path, **summarise(u)})
out = pd.DataFrame(rows).sort_values(["weather_year", "variant"])
out.to_csv(sys.argv[1], index=False)
print(out.drop(columns="source").to_string(index=False))
