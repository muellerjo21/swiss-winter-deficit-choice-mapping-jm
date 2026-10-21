"""Sensitivity to the ElCom reference price: curve, crossing points and base years (src/sensitivity.py)."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import LANGUAGE_REGION_WEIGHTS
from load_data import (
    load_beta_partworths_mean, load_beta_partworths_samples,
    load_mobile_partworths_mean, load_mobile_partworths_samples, load_scenario_cost_and_demand,
)
from sensitivity import (
    check_completed_years, reference_price_grid, reference_price_curve, crossing_points, base_year_table,
)
from utility import load_attribute_scale


def load_model(path_to_choice_model: str, mobile_share: float, weights: dict = LANGUAGE_REGION_WEIGHTS) -> dict:
    """Betas loaded once, as keyword arguments of utility.rank_with_uncertainty."""
    return {
        "scale": load_attribute_scale(path_to_choice_model),
        "betas_mean": {r: load_beta_partworths_mean(path_to_choice_model, r) for r in weights},
        "betas_samples": {r: load_beta_partworths_samples(path_to_choice_model, r) for r in weights},
        "weights": weights,
        "mobile_mean": load_mobile_partworths_mean(path_to_choice_model),
        "mobile_samples": load_mobile_partworths_samples(path_to_choice_model),
        "mobile_share": mobile_share,
    }


def load_year_files(paths_to_elcom: list[str], paths_to_eur_chf: list[str]) -> tuple[dict, dict]:
    keys = ("total_rp_kwh", "taxes_levies_rp_kwh", "netznutzung_rp_kwh")
    elcom = {}
    for p in paths_to_elcom:
        d = json.loads(Path(p).read_text())
        elcom[d["year"]] = {k: d[k] for k in keys}
    rates = {}
    for p in paths_to_eur_chf:
        d = json.loads(Path(p).read_text())
        rates[d["year"]] = (d["eur_to_chf"], d["n_days"])
    return elcom, rates


def sensitivity(path_to_attributes: str, path_to_choice_model: str, paths_to_nc: list[str], scenario_ids: list[str],
                paths_to_elcom: list[str], paths_to_eur_chf: list[str], reference_year: int, base_years: list[int],
                reference_price: dict, crossing_scenarios: list[str], crossing_tolerance: float,
                crossing_check_delta: float, mobile_share: float,
                path_to_curve: str, path_to_crossings: str, path_to_base_years: str) -> None:
    check_completed_years(base_years)
    attributes = pd.read_csv(path_to_attributes)
    scenario_cost = {s: load_scenario_cost_and_demand(p) for s, p in zip(scenario_ids, paths_to_nc)}
    model = load_model(path_to_choice_model, mobile_share)
    elcom, rates = load_year_files(paths_to_elcom, paths_to_eur_chf)
    ref, (rate, _) = elcom[reference_year], rates[reference_year]

    grid = reference_price_grid(reference_price["start"], reference_price["stop"], reference_price["step"])
    reference_price_curve(attributes, scenario_cost, ref, rate, grid, model).to_csv(path_to_curve, index=False)

    crossings = crossing_points(attributes, scenario_cost, ref, rate, model, *crossing_scenarios,
                                low=float(grid[0]), high=float(grid[-1]),
                                tolerance=crossing_tolerance, check_delta=crossing_check_delta)
    for col, value in [("reference_year", reference_year), ("taxes_levies_rp_kwh", ref["taxes_levies_rp_kwh"]),
                       ("netznutzung_rp_kwh", ref["netznutzung_rp_kwh"]), ("eur_to_chf", rate)]:
        crossings[col] = value
    crossings.to_csv(path_to_crossings, index=False)

    base_year_table(attributes, scenario_cost, {y: elcom[y] for y in base_years}, {y: rates[y] for y in base_years},
                    model).to_csv(path_to_base_years, index=False)


if __name__ == "__main__":
    p = snakemake.params
    sensitivity(
        path_to_attributes=snakemake.input.attributes,
        path_to_choice_model=snakemake.input.choice_model,
        paths_to_nc=list(snakemake.input.nc),
        scenario_ids=p.scenario_ids,
        paths_to_elcom=list(snakemake.input.elcom),
        paths_to_eur_chf=list(snakemake.input.eur_chf),
        reference_year=p.reference_year,
        base_years=p.base_years,
        reference_price=p.reference_price,
        crossing_scenarios=p.crossing_scenarios,
        crossing_tolerance=p.crossing_tolerance,
        crossing_check_delta=p.crossing_check_delta,
        mobile_share=p.mobile_share,
        path_to_curve=snakemake.output.curve,
        path_to_crossings=snakemake.output.crossings,
        path_to_base_years=snakemake.output.base_years,
    )
