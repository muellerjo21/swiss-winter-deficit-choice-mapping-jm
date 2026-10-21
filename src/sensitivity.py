"""
Sensitivity of the scenario ranking to the ElCom reference price.

- Curve: P(rank 1), rank and utility of all scenarios as a function of the reference price
  (total_rp_kwh); taxes/levies, grid usage and EUR/CHF rate stay at the reference year, only the
  reference price varies.
- Crossing points: reference price at which two scenarios swap rank (posterior-mean utility equal),
  per region and national, by bisection.
- Base years: price_change, rank and P(rank 1) per base year with that year's own ElCom reference
  values and annual EUR/CHF rate.

The price formula (load_data.price_change_from_cost) and the ranking (utility.rank_with_uncertainty)
are the ones of the main pipeline; system cost and demand per scenario are read once by the caller.
"""
from datetime import date

import numpy as np
import pandas as pd

from load_data import price_change_from_cost
from utility import rank_with_uncertainty


def check_completed_years(years) -> None:
    """Base years need a completed calendar year (annual mean EUR/CHF rate, see fetch_eur_to_chf)."""
    open_years = [y for y in years if y >= date.today().year]
    if open_years:
        raise ValueError(f"Base years must be completed calendar years, got {open_years} "
                         f"(current year {date.today().year}).")


def reference_price_grid(start: float, stop: float, step: float) -> np.ndarray:
    """start, start+step, ..., stop (inclusive), rounded against floating-point drift."""
    n = int(round((stop - start) / step))
    return np.round(start + step * np.arange(n + 1), 10)


def rankings_at(attributes: pd.DataFrame, scenario_cost: dict, elcom_ref: dict, eur_to_chf: float,
                model: dict) -> pd.DataFrame:
    """Rankings (as utility_rankings.csv) with price_change recomputed for elcom_ref / eur_to_chf.
    scenario_cost: scenario_id -> (system_cost, demand); model: keyword arguments of
    rank_with_uncertainty (betas_mean, betas_samples, scale, weights, mobile_*)."""
    attrs = attributes.copy()
    attrs["price_change"] = [price_change_from_cost(*scenario_cost[s], elcom_ref, eur_to_chf)
                             for s in attrs["scenario_id"]]
    return rank_with_uncertainty(attrs, **model).set_index("scenario_id")


def region_tags(weights: dict) -> list[str]:
    return [r.replace("-", "_") for r in weights] + ["national"]


def _long(rankings: pd.DataFrame, tags: list[str]) -> pd.DataFrame:
    """Wide rankings -> one row per scenario and region with rank, p_rank1, utility."""
    return pd.concat([
        pd.DataFrame({"scenario_id": rankings.index, "region": tag,
                      "rank": rankings[f"rank_{tag}"].to_numpy(),
                      "p_rank1": rankings[f"p_rank1_{tag}"].to_numpy(),
                      "utility": rankings[f"utility_{tag}"].to_numpy()})
        for tag in tags], ignore_index=True)


def reference_price_curve(attributes: pd.DataFrame, scenario_cost: dict, elcom_ref: dict, eur_to_chf: float,
                          grid: np.ndarray, model: dict) -> pd.DataFrame:
    """Curve over the grid plus the reference year's own total_rp_kwh (is_reference_year=True), so that
    the curve can be checked against utility_rankings.csv."""
    tags = region_tags(model["weights"])
    ref_total = elcom_ref["total_rp_kwh"]
    points = sorted(set(float(x) for x in grid) | {ref_total})
    frames = []
    for total in points:
        rk = rankings_at(attributes, scenario_cost, {**elcom_ref, "total_rp_kwh": total}, eur_to_chf, model)
        df = _long(rk, tags)
        df.insert(0, "is_reference_year", total == ref_total)
        df.insert(0, "total_rp_kwh", total)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def crossing_point(attributes: pd.DataFrame, scenario_cost: dict, elcom_ref: dict, eur_to_chf: float,
                   model: dict, tag: str, scenario_a: str, scenario_b: str, low: float, high: float,
                   tolerance: float) -> float:
    """Reference price in [low, high] at which utility_a - utility_b (posterior-mean betas) changes sign,
    by bisection. NaN if there is no sign change in the interval."""
    def diff(total):
        rk = rankings_at(attributes, scenario_cost, {**elcom_ref, "total_rp_kwh": total}, eur_to_chf, model)
        return rk.loc[scenario_a, f"utility_{tag}"] - rk.loc[scenario_b, f"utility_{tag}"]

    d_low, d_high = diff(low), diff(high)
    if np.sign(d_low) == np.sign(d_high):
        return float("nan")
    while high - low > tolerance:
        mid = (low + high) / 2
        d_mid = diff(mid)
        if np.sign(d_mid) == np.sign(d_low):
            low, d_low = mid, d_mid
        else:
            high = mid
    return (low + high) / 2


def crossing_points(attributes: pd.DataFrame, scenario_cost: dict, elcom_ref: dict, eur_to_chf: float,
                    model: dict, scenario_a: str, scenario_b: str, low: float, high: float,
                    tolerance: float, check_delta: float) -> pd.DataFrame:
    """Crossing point per region, with the ranks of both scenarios check_delta below and above it."""
    rows = []
    below_above = {}
    for tag in region_tags(model["weights"]):
        x = crossing_point(attributes, scenario_cost, elcom_ref, eur_to_chf, model, tag,
                           scenario_a, scenario_b, low, high, tolerance)
        row = {"region": tag, "scenario_a": scenario_a, "scenario_b": scenario_b, "crossing_rp_kwh": x}
        for side, total in [("below", x - check_delta), ("above", x + check_delta)]:
            if (side, total) not in below_above:
                below_above[(side, total)] = rankings_at(attributes, scenario_cost,
                                                         {**elcom_ref, "total_rp_kwh": total}, eur_to_chf, model)
            rk = below_above[(side, total)]
            row[f"rank_a_{side}"] = int(rk.loc[scenario_a, f"rank_{tag}"])
            row[f"rank_b_{side}"] = int(rk.loc[scenario_b, f"rank_{tag}"])
        rows.append(row)
    return pd.DataFrame(rows)


def base_year_table(attributes: pd.DataFrame, scenario_cost: dict, elcom_refs: dict, rates: dict,
                    model: dict) -> pd.DataFrame:
    """price_change, rank, P(rank 1) and utility per base year, scenario and region.
    elcom_refs: year -> get_elcom_reference_price dict; rates: year -> (eur_to_chf, n_days)."""
    tags = region_tags(model["weights"])
    frames = []
    for year in sorted(elcom_refs):
        ref, (rate, n_days) = elcom_refs[year], rates[year]
        rk = rankings_at(attributes, scenario_cost, ref, rate, model)
        attrs = attributes.set_index("scenario_id")
        price_change = {s: price_change_from_cost(*scenario_cost[s], ref, rate) for s in attrs.index}
        df = _long(rk, tags)
        df.insert(1, "price_change", df["scenario_id"].map(price_change))
        for i, (col, value) in enumerate([("year", year), ("total_rp_kwh", ref["total_rp_kwh"]),
                                          ("taxes_levies_rp_kwh", ref["taxes_levies_rp_kwh"]),
                                          ("netznutzung_rp_kwh", ref["netznutzung_rp_kwh"]),
                                          ("eur_to_chf", rate), ("n_days", n_days)]):
            df.insert(i, col, value)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
