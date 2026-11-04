"""Comparison of the weather years (rule weather_year_rankings): one row per weather year, scenario and group with rank,
P(rank 1), utility and credible interval, over the scenarios of each year (set all) and over the scenarios available in
every weather year (set common); scenarios without a result file for a year are listed as missing."""
import pandas as pd

GROUPS = ["national", "DE_CH", "FR_CH"]


def long_table(rankings: pd.DataFrame, scenario_set: str) -> pd.DataFrame:
    rows = []
    for _, r in rankings.iterrows():
        for g in GROUPS:
            low = next(c for c in rankings.columns if c.startswith(f"utility_{g}_") and c.endswith("_low"))
            high = next(c for c in rankings.columns if c.startswith(f"utility_{g}_") and c.endswith("_high"))
            rows.append({"weather_year": int(r["weather_year"]), "scenario_set": scenario_set, "group": g,
                         "scenario_id": r["scenario_id"], "rank": int(r[f"rank_{g}"]), "p_rank1": r[f"p_rank1_{g}"],
                         "utility": r[f"utility_{g}"], "utility_interval_low": r[low], "utility_interval_high": r[high],
                         "n_scenarios": int(r["n_scenarios"])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    tables = [long_table(pd.read_csv(p), "all") for p in snakemake.input.rankings]
    tables += [long_table(pd.read_csv(p), "common") for p in snakemake.input.rankings_common]
    out = pd.concat(tables, ignore_index=True).sort_values(["scenario_set", "group", "weather_year", "rank"])
    out.to_csv(snakemake.output.summary, index=False)
    missing = [{"weather_year": int(y), "scenario_id": s} for s, files in snakemake.params.scenarios.items()
               for y in snakemake.params.weather_years if not (files.get(y) or files.get(str(y)))]
    pd.DataFrame(missing, columns=["weather_year", "scenario_id"]).to_csv(snakemake.output.missing, index=False)
