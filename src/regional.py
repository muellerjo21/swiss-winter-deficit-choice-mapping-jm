"""
Regional analysis on the 23 Swiss locations of the Calliope model (20 cantons, the merged regions AI_AR,
BL_BS, NW_OW, and TI).

- Attributes per region r and scenario: land use, technology and ownership shares from the region's own
  capacities; price change with the national system cost per kWh and the region's ElCom reference price
  and surcharges; import share national (import from abroad, same value in every region); transmission 0.
- Utility per region with the coefficients of the region's language region (CANTON_LANGUAGE), draw by
  draw: posterior draw i of a language region is used for all regions of that language region.
- Aggregation: population-weighted mean of the utility samples (and point utilities) over the included
  regions, per language region and nationally; rank, credible interval and P(rank 1) as in the national
  analysis (utility.rankings_from_utilities).
"""
import numpy as np
import pandas as pd
import xarray as xr

from config import ATTRIBUTE_COLUMN_TO_MODEL_TERM, CANTON_LANGUAGE, CANTON_MERGES, FOREIGN_CODES
from load_data import (
    compute_land_from_capacity, compute_ownership_shares, compute_technology_mix_shares,
    elcom_reference_from_prices, load_scenario_capacity, price_change_from_cost,
)
from utility import compute_utility, compute_utility_samples, probability_rank1, rank_scenarios, rankings_from_utilities

LANGUAGE_GROUPS = ["DE-CH", "FR-CH"]


def region_of_canton(canton: str) -> str:
    """Canton abbreviation -> Calliope region (merged codes for AI/AR, BL/BS, NW/OW)."""
    return next((merged for merged, parts in CANTON_MERGES.items() if canton in parts), canton)


def municipality_regions(cantons: pd.DataFrame, overrides: dict) -> pd.Series:
    """bfs_nr -> Calliope region, from fetch_municipality_cantons plus overrides {bfs_nr: canton} for
    municipalities without a canton in the register."""
    canton = dict(zip(cantons["bfs_nr"], cantons["canton"]))
    canton.update({int(k): v for k, v in overrides.items()})
    return pd.Series({nr: region_of_canton(c) for nr, c in canton.items()}, name="region")


def regional_elcom_reference(prices: pd.DataFrame, regions: pd.Series) -> pd.DataFrame:
    """ElCom reference values per Calliope region (median over the region's tariff rows, same definition as
    the national reference, load_data.elcom_reference_from_prices). prices as from fetch_elcom_price."""
    p = prices.copy()
    p["bfs_nr"] = p["municipality_id"].str.rsplit("/", n=1).str[-1].astype(int)
    p["region"] = p["bfs_nr"].map(regions)
    if p["region"].isna().any():
        raise ValueError(f"ElCom municipalities without region: {sorted(p.loc[p['region'].isna(), 'bfs_nr'].unique())}")
    rows = {r: {**elcom_reference_from_prices(g), "n_rows": len(g), "n_municipalities": g["bfs_nr"].nunique()}
            for r, g in p.groupby("region")}
    return pd.DataFrame(rows).T


def regional_population(statpop: pd.DataFrame, regions: pd.Series) -> pd.Series:
    """Population per Calliope region (sum over its municipalities)."""
    region = statpop["bfs_nr"].map(regions)
    if region.isna().any():
        raise ValueError(f"STATPOP municipalities without region: {sorted(statpop.loc[region.isna(), 'bfs_nr'])}")
    return statpop.groupby(region)["population"].sum().rename("population")


def population_weights(population: pd.Series, exclude: list) -> pd.Series:
    """Population weights of the included regions, normalised to sum 1."""
    p = population.drop([r for r in exclude if r in population.index])
    return (p / p.sum()).rename("weight")


def _shares(capacity: pd.DataFrame) -> dict:
    """Technology and ownership shares of one region; 0 instead of NaN if a denominator is empty."""
    out = {**compute_technology_mix_shares(capacity), **compute_ownership_shares(capacity)}
    return {k: (0.0 if pd.isna(v) else float(v)) for k, v in out.items()}


def regional_attributes(nc_path: str, scenario_id: str, area: dict, national: pd.Series, system_cost: float,
                        demand: float, elcom: pd.DataFrame, eur_to_chf: float) -> pd.DataFrame:
    """Attributes of one scenario per Calliope region (rows), columns as in scenario_attributes_summary.
    national: the scenario's national attribute row (import_share, mellot_cost_change_pct and, for the
    comparison, relative_land of the national definition)."""
    capacity = load_scenario_capacity(nc_path)
    land = compute_land_from_capacity(capacity, area).groupby("canton")["land_use_km2"].sum()
    rows = []
    for region in sorted(capacity["canton"].unique()):
        ref = elcom.loc[region, ["total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh"]].astype(float).to_dict()
        rows.append({
            "scenario_id": scenario_id, "region": region, "language": CANTON_LANGUAGE.get(region),
            "transmission_change": 0.0,
            "relative_land": land.get(region, 0.0) / area[region],
            "import_share": national["import_share"],
            **_shares(capacity[capacity["canton"] == region]),
            "price_change": price_change_from_cost(system_cost, demand, ref, eur_to_chf),
            "mellot_cost_change_pct": national["mellot_cost_change_pct"],
            "relative_land_national": national["relative_land"],
        })
    return pd.DataFrame(rows)


def regional_balance_import_share(nc_path: str) -> pd.Series:
    """Sensitivity: import share from the region's own electricity balance,
    max(0, consumption - generation) / consumption, with generation = electricity output of all
    non-transmission technologies and consumption = demand_elec plus sector coupling (as nationally)."""
    from load_data import get_ch_total_electricity_demand_techs
    ds = xr.open_dataset(nc_path)
    prod = ds["carrier_prod"].sum("timesteps").to_pandas()
    con = ds["carrier_con"].sum("timesteps").to_pandas()
    demand_techs = get_ch_total_electricity_demand_techs(ds)
    ds.close()
    loc = pd.Series(prod.index.str.split("::").str[0], index=prod.index)
    gen_mask = prod.index.str.endswith("::electricity") & ~prod.index.str.contains("::ac_transmission") & ~loc.isin(FOREIGN_CODES)
    generation = prod[gen_mask].groupby(loc[gen_mask]).sum()
    demand = (-con.loc[demand_techs]).groupby(pd.Index([d.split("::")[0] for d in demand_techs])).sum()
    return ((demand - generation.reindex(demand.index).fillna(0.0)) / demand).clip(lower=0.0, upper=1.0)


def language_coefficients(betas_mean: dict, betas_samples: dict, language_weights: dict) -> tuple[dict, dict]:
    """Adds 'mixed' = language-weighted coefficients (draw by draw) to the per-language coefficients, for
    regions without own coefficients (TI sensitivity)."""
    mean, samples = dict(betas_mean), dict(betas_samples)
    first = betas_mean[LANGUAGE_GROUPS[0]].set_index("attribute")["beta_mean"]
    mean["mixed"] = pd.DataFrame({"attribute": first.index, "beta_mean": sum(
        w * betas_mean[l].set_index("attribute")["beta_mean"].loc[first.index] for l, w in language_weights.items()).to_numpy()})
    samples["mixed"] = {t: sum(w * betas_samples[l][t] for l, w in language_weights.items()) for t in betas_samples[LANGUAGE_GROUPS[0]]}
    return mean, samples


def regional_utilities(attributes: pd.DataFrame, weights: pd.Series, coefficient_of_region: dict, betas_mean: dict,
                       betas_samples: dict, scale: dict, mobile_mean=None, mobile_samples=None,
                       mobile_share: float = 0.0, with_samples: bool = True) -> tuple:
    """Utility per included region (point estimate and posterior samples, coefficients
    coefficient_of_region[region] in betas_mean/betas_samples), aggregated with the population weights per
    language region and nationally. Returns (utilities, samples, region_points, region_samples) with
    utilities/samples in the format of utility.compute_regional_utilities (groups DE-CH, FR-CH, national).
    with_samples=False skips the posterior samples (point utilities only, e.g. for bisection)."""
    scenarios = attributes["scenario_id"].drop_duplicates().tolist()
    region_points, region_samples = {}, {}
    for region in weights.index:
        coef = coefficient_of_region[region]
        a = attributes[attributes["region"] == region].set_index("scenario_id").loc[scenarios]
        region_points[region] = pd.Series({s: compute_utility(r, betas_mean[coef], scale, mobile=mobile_mean,
                                                              mobile_share=mobile_share) for s, r in a.iterrows()})
        if with_samples:
            region_samples[region] = pd.DataFrame({s: compute_utility_samples(r, betas_samples[coef], scale,
                                                                              mobile_samples=mobile_samples,
                                                                              mobile_share=mobile_share) for s, r in a.iterrows()})
    groups = {g: [r for r in weights.index if CANTON_LANGUAGE.get(r) == g] for g in LANGUAGE_GROUPS}
    groups["national"] = list(weights.index)
    utilities = pd.DataFrame({"scenario_id": scenarios})
    samples = {}
    for g, members in groups.items():
        w = weights[members] / weights[members].sum()
        utilities[f"utility_{g.replace('-', '_')}"] = sum(w[r] * region_points[r] for r in members).loc[scenarios].to_numpy()
        if with_samples:
            samples[g] = sum(w[r] * region_samples[r] for r in members)
    return utilities, samples, region_points, region_samples


def regional_rankings(attributes: pd.DataFrame, utilities: pd.DataFrame, samples: dict, credible_interval: float) -> pd.DataFrame:
    """Rankings in the format of utility_rankings.csv (groups DE-CH, FR-CH, national)."""
    first = attributes.drop_duplicates("scenario_id")[["scenario_id", "mellot_cost_change_pct"]]
    return rankings_from_utilities(utilities, samples, [*LANGUAGE_GROUPS, "national"], first, credible_interval)


def region_table(region_points: dict, region_samples: dict, weights: pd.Series, population: pd.Series,
                 coefficient_of_region: dict) -> pd.DataFrame:
    """Per region and scenario: utility (posterior mean coefficients), rank, P(rank 1), population, weight."""
    rows = []
    for region, u in region_points.items():
        ranks = rank_scenarios(u.rename("u").rename_axis("scenario_id").reset_index(), "u").set_index("scenario_id")["rank"]
        p1 = probability_rank1(region_samples[region])
        for s in u.index:
            rows.append({"region": region, "language": CANTON_LANGUAGE.get(region), "coefficients": coefficient_of_region[region],
                         "population": population[region], "weight": weights[region], "scenario_id": s,
                         "utility": u[s], "rank": int(ranks[s]), "p_rank1": p1[s]})
    return pd.DataFrame(rows)


def rank1_population_share(table: pd.DataFrame) -> pd.Series:
    """Population share (of the included regions) for which each scenario is rank 1 (posterior mean)."""
    first = table[table["rank"] == 1]
    return first.groupby("scenario_id")["weight"].sum().reindex(table["scenario_id"].unique(), fill_value=0.0)


def attribute_columns() -> list[str]:
    return list(ATTRIBUTE_COLUMN_TO_MODEL_TERM)


def with_shifted_reference(attributes: pd.DataFrame, cost_and_demand: dict, elcom: pd.DataFrame, eur_to_chf: float,
                           shift: float) -> pd.DataFrame:
    """Attributes with price_change recomputed for all regional reference prices shifted by the same amount
    (Rp./kWh); taxes/levies and grid usage of the regions unchanged."""
    a = attributes.copy()
    refs = {r: {**elcom.loc[r, ["taxes_levies_rp_kwh", "netznutzung_rp_kwh"]].astype(float).to_dict(),
                "total_rp_kwh": float(elcom.loc[r, "total_rp_kwh"]) + shift} for r in a["region"].unique()}
    a["price_change"] = [price_change_from_cost(*cost_and_demand[s], refs[r], eur_to_chf) for s, r in zip(a["scenario_id"], a["region"])]
    return a


def regional_price_curve(attributes, cost_and_demand, elcom, eur_to_chf, shifts, rank_at) -> pd.DataFrame:
    """Rank, P(rank 1) and utility per group (DE-CH, FR-CH, national) over the common shift of all regional
    reference prices; rank_at(attributes) -> rankings (regional_rankings). Shift 0 is always included."""
    frames = []
    for shift in sorted(set(float(x) for x in shifts) | {0.0}):
        rk = rank_at(with_shifted_reference(attributes, cost_and_demand, elcom, eur_to_chf, shift)).set_index("scenario_id")
        for g in [*LANGUAGE_GROUPS, "national"]:
            t = g.replace("-", "_")
            frames.append(pd.DataFrame({"shift_rp_kwh": shift, "is_reference_year": shift == 0.0, "region": t,
                                        "scenario_id": rk.index, "rank": rk[f"rank_{t}"].to_numpy(),
                                        "p_rank1": rk[f"p_rank1_{t}"].to_numpy(), "utility": rk[f"utility_{t}"].to_numpy()}))
    return pd.concat(frames, ignore_index=True)


def regional_rank1_switches(attributes, cost_and_demand, elcom, eur_to_chf, curve, leader_at, tolerance: float,
                            check_delta: float) -> pd.DataFrame:
    """Shifts at which the rank-1 scenario (posterior-mean utility) of a group changes, refined by bisection
    (sensitivity.bisect_change); leader_at(attributes, group) -> scenario on rank 1."""
    from sensitivity import bisect_change
    rows = []
    grid = curve[~curve["is_reference_year"] | (curve["shift_rp_kwh"] == 0.0)]
    for tag in grid["region"].unique():
        leader = grid[(grid["region"] == tag) & (grid["rank"] == 1)].set_index("shift_rp_kwh")["scenario_id"].sort_index()
        items = list(leader.items())
        for (low, before), (high, after) in zip(items, items[1:]):
            if before == after:
                continue
            at = lambda shift: leader_at(with_shifted_reference(attributes, cost_and_demand, elcom, eur_to_chf, shift), tag)
            x, after = bisect_change(at, low, high, before, after, tolerance)
            row = {"region": tag, "switch_shift_rp_kwh": x, "scenario_before": before, "scenario_after": after}
            for side, shift in [("below", x - check_delta), ("above", x + check_delta)]:
                row[f"rank1_{side}"] = leader_at(with_shifted_reference(attributes, cost_and_demand, elcom, eur_to_chf, shift), tag)
            rows.append(row)
    return pd.DataFrame(rows, columns=["region", "switch_shift_rp_kwh", "scenario_before", "scenario_after", "rank1_below", "rank1_above"])


def load_regional_model(path_to_choice_model: str, mobile_share: float, language_weights: dict) -> dict:
    """Coefficients loaded once as keyword arguments of regional_utilities: per language region plus 'mixed'."""
    from load_data import (load_beta_partworths_mean, load_beta_partworths_samples, load_mobile_partworths_mean,
                           load_mobile_partworths_samples)
    from utility import load_attribute_scale
    mean = {l: load_beta_partworths_mean(path_to_choice_model, l) for l in LANGUAGE_GROUPS}
    samples = {l: load_beta_partworths_samples(path_to_choice_model, l) for l in LANGUAGE_GROUPS}
    mean, samples = language_coefficients(mean, samples, language_weights)
    return {"betas_mean": mean, "betas_samples": samples, "scale": load_attribute_scale(path_to_choice_model),
            "mobile_mean": load_mobile_partworths_mean(path_to_choice_model),
            "mobile_samples": load_mobile_partworths_samples(path_to_choice_model), "mobile_share": mobile_share}
