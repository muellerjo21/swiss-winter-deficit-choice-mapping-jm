"""Maps of the regional choice probabilities (as in Tröndle et al. 2025, Fig. 1/3): region geometries from
swisstopo swissBOUNDARIES3D (cantons, LV95), merged to the regions of the Calliope model. Runs in envs/maps.yaml
(geopandas); imports only light modules (config, plot_style)."""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch

from config import CANTON_MERGES, CANTON_NUMBER_TO_CODE, SCENARIO_DISPLAY_NAMES
from plot_style import CHOICE_CMAP, NEUTRAL, TEXT_SECONDARY, save


def region_of_canton(canton: str) -> str:
    return next((merged for merged, parts in CANTON_MERGES.items() if canton in parts), canton)


def load_region_geometries(zip_path: str, member: str, layer: str, crs: str, tolerance: float) -> gpd.GeoDataFrame:
    """Cantons from the zipped GeoPackage, 2D, in `crs`, dissolved to the Calliope regions (merged cantons) and
    simplified as a coverage (shared borders stay identical, no gaps or overlaps)."""
    cantons = gpd.read_file(f"/vsizip/{zip_path}/{member}", layer=layer).to_crs(crs)
    cantons["canton"] = cantons["kantonsnummer"].map(CANTON_NUMBER_TO_CODE)
    if cantons["canton"].isna().any():
        raise ValueError(f"unknown canton numbers: {sorted(cantons.loc[cantons['canton'].isna(), 'kantonsnummer'])}")
    cantons["region"] = cantons["canton"].map(region_of_canton)
    cantons["geometry"] = shapely.force_2d(cantons.geometry.values)
    regions = cantons.dissolve(by="region", aggfunc={"canton": lambda c: "+".join(sorted(c))}).reset_index()
    regions = regions.rename(columns={"canton": "cantons"}).sort_values("region").reset_index(drop=True)
    if tolerance > 0:
        regions["geometry"] = shapely.coverage_simplify(regions.geometry.values, tolerance)
    return regions


def geometry_checks(geometries: gpd.GeoDataFrame, analysis_regions: list) -> pd.DataFrame:
    """Per region code of the analysis: number of matching geometries (must be exactly 1), plus geometries
    without a region of the analysis."""
    counts = geometries["region"].value_counts()
    rows = [{"region": r, "n_geometries": int(counts.get(r, 0)),
             "cantons": "+".join(geometries.loc[geometries["region"] == r, "cantons"]),
             "area_km2": float(geometries.loc[geometries["region"] == r].area.sum() / 1e6)} for r in analysis_regions]
    rows += [{"region": r, "n_geometries": int(counts[r]), "cantons": "", "area_km2": np.nan}
             for r in counts.index if r not in analysis_regions]
    out = pd.DataFrame(rows)
    valid = dict(zip(geometries["region"], geometries.is_valid))
    out["valid"] = out["region"].map(valid).fillna(False).astype(bool)
    out["coverage_valid"] = bool(shapely.coverage_is_valid(geometries.geometry.values))
    out["in_analysis"] = out["region"].isin(analysis_regions)
    out["passed"] = out["in_analysis"] & (out["n_geometries"] == 1) & out["valid"] & out["coverage_valid"]
    return out


def _draw(ax, geometries: gpd.GeoDataFrame, values: pd.Series, excluded: list, title: str, title_size: float):
    data = geometries.assign(value=geometries["region"].map(values))
    shown = data[data["value"].notna()]
    shown.plot(ax=ax, column="value", cmap=CHOICE_CMAP, vmin=0, vmax=1, edgecolor="white", linewidth=0.6)
    data[data["region"].isin(excluded)].plot(ax=ax, color="#d9d8d4", edgecolor="white", linewidth=0.6,
                                             hatch="///")
    ax.set_title(title, loc="left", fontweight="bold", fontsize=title_size)
    ax.set_axis_off()
    ax.set_aspect("equal")


def fig_choice_map(geometries: gpd.GeoDataFrame, table: pd.DataFrame, excluded: list, credible_interval: float,
                   out_dir, name: str, formats=("png", "pdf")) -> None:
    """(A) expected value (large), (B) upper and (C) lower bound of the credible interval of P(scenario 1 >
    scenario 2) per region; common colour bar 0-100 %."""
    a, b = table["scenario_1"].iloc[0], table["scenario_2"].iloc[0]
    t = table.set_index("region")
    fig = plt.figure(figsize=(12, 7.2))
    grid = GridSpec(3, 3, figure=fig, width_ratios=[1, 1, 0.95], height_ratios=[1, 1, 0.09], hspace=0.12, wspace=0.02)
    ax_a = fig.add_subplot(grid[0:2, 0:2])
    ax_b = fig.add_subplot(grid[0, 2])
    ax_c = fig.add_subplot(grid[1, 2])
    _draw(ax_a, geometries, t["p_mean"], excluded, "(A) Expected value", 13)
    _draw(ax_b, geometries, t["p_high"], excluded, "(B) Upper uncertainty bound", 11)
    _draw(ax_c, geometries, t["p_low"], excluded, "(C) Lower uncertainty bound", 11)
    ax_a.legend(handles=[Patch(facecolor="#d9d8d4", edgecolor="white", hatch="///", label="No data (TI)")],
                loc="lower left", frameon=False)
    cax = fig.add_subplot(grid[2, :])
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(0, 1), cmap=CHOICE_CMAP), cax=cax,
                       orientation="horizontal")
    bar.set_ticks([0, 0.25, 0.5, 0.75, 1])
    bar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
    bar.outline.set_visible(False)
    name_a, name_b = SCENARIO_DISPLAY_NAMES.get(a, a), SCENARIO_DISPLAY_NAMES.get(b, b)
    bar.set_label(f"Choice probability {name_a} (1)", fontsize=11.5)
    fig.suptitle(f"{name_a} (1) vs. {name_b} (2)", x=0.125, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.125, 0.0, f"Probability that {name_a} is chosen over {name_b} in a pairwise comparison, per region "
             f"(posterior mean; bounds: {credible_interval * 100:g}% equal-tailed credible interval).\n"
             "Regions of the Calliope model (AI/AR, BL/BS, NW/OW merged). Boundaries: swisstopo swissBOUNDARIES3D, "
             "LV95 (EPSG:2056).", fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir, formats)
