"""Language map (fig12): (A) majority main language per canton (BFS structural survey) with the language border of
the BFS language areas (municipalities), (B) coefficient group of every Calliope region in this project
(regions.language, spatial.regional.ticino). Figure only, no input of the analysis. Runs in envs/maps.yaml."""
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib import patheffects
from matplotlib.colors import ListedColormap, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from config import CANTON_LANGUAGE, CANTON_NUMBER_TO_CODE, region_of_canton
from plot_style import EXCLUDED_FILL, SERIES, TEXT_PRIMARY, TEXT_SECONDARY, save

LIGHTEST = 0.25   # colour intensity at the lower end of share_range (fraction of the full colour, rest white)


def language_colors(languages: dict) -> dict:
    """Colour per language of maps.languages.majority_of: the categorical palette in this order (blue, orange,
    green), the same colour for a language and its coefficient group."""
    return dict(zip(languages["majority_of"], SERIES))


def load_cantons(zip_path: str, member: str, layer: str, crs: str, tolerance: float) -> gpd.GeoDataFrame:
    """The 26 cantons (2D, `crs`) with their Calliope region, simplified as a coverage."""
    cantons = gpd.read_file(f"/vsizip/{zip_path}/{member}", layer=layer).to_crs(crs)
    cantons["canton"] = cantons["kantonsnummer"].map(CANTON_NUMBER_TO_CODE)
    if cantons["canton"].isna().any():
        raise ValueError(f"unknown canton numbers: {sorted(cantons.loc[cantons['canton'].isna(), 'kantonsnummer'])}")
    cantons["geometry"] = shapely.force_2d(cantons.geometry.values)
    cantons = cantons.dissolve(by="canton").reset_index()[["canton", "geometry"]]
    if tolerance > 0:
        cantons["geometry"] = shapely.coverage_simplify(cantons.geometry.values, tolerance)
    cantons["region"] = cantons["canton"].map(region_of_canton)
    return cantons


def language_borders(zip_path: str, member: str, layer: str, crs: str, tolerance: float,
                     municipalities: pd.DataFrame) -> gpd.GeoSeries:
    """Lines between municipalities of different language areas. Every municipality of the table must have a
    geometry; areas without a language (lakes, joint territories) get no line."""
    shapes = gpd.read_file(f"/vsizip/{zip_path}/{member}", layer=layer, columns=["bfs_nummer", "icc"])
    shapes = shapes[shapes["icc"] == "CH"].to_crs(crs)
    shapes["geometry"] = shapely.force_2d(shapes.geometry.values)
    if tolerance > 0:
        shapes["geometry"] = shapely.coverage_simplify(shapes.geometry.values, tolerance)
    missing = set(municipalities["municipality"]) - set(shapes["bfs_nummer"])
    if missing:
        raise ValueError(f"municipalities without geometry: {sorted(missing)}")
    areas = shapes.merge(municipalities, left_on="bfs_nummer", right_on="municipality").dissolve(by="language")
    lines = []
    keys = list(areas.index)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            shared = shapely.intersection(areas.geometry[a].boundary, areas.geometry[b].boundary)
            if not shared.is_empty:
                lines.append(shapely.line_merge(shapely.union_all(
                    [g for g in shapely.get_parts(shared) if g.geom_type in ("LineString", "MultiLineString")])))
    return gpd.GeoSeries(lines, crs=crs)


def tint(color: str, t: float) -> tuple:
    """Colour at intensity t (0 = lightest, 1 = full colour), blended with white."""
    w = LIGHTEST + (1 - LIGHTEST) * float(np.clip(t, 0, 1))
    return tuple(1 - w + w * c for c in to_rgb(color))


def _labels(ax, geometries: gpd.GeoDataFrame, column: str):
    for _, row in geometries.iterrows():
        point = row.geometry.representative_point()
        ax.text(point.x, point.y, row[column].replace("_", "/"), ha="center", va="center", fontsize=7,
                color=TEXT_PRIMARY, path_effects=[patheffects.withStroke(linewidth=2, foreground="white")])


def _frame(ax, title: str):
    ax.set_title(title, loc="left", fontweight="bold", fontsize=12.5)
    ax.set_axis_off()
    ax.set_aspect("equal")


def fig_language_map(cantons: gpd.GeoDataFrame, shares: pd.DataFrame, borders: gpd.GeoSeries, languages: dict,
                     areas: dict, ticino: str, choice_model: str, coefficients: dict, boundaries_release: str,
                     out_dir, name: str, formats) -> None:
    lo, hi = languages["share_range"]
    names = languages["names"]
    colors_of = language_colors(languages)
    group_color = {g: colors_of[lang] for g, lang in languages["group_language"].items()}
    s = shares.set_index("canton")
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13, 6.6), gridspec_kw={"wspace": 0.04})
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.3)

    # (A) majority language per canton, intensity = its share
    colors = [tint(colors_of[s.at[c, "majority"]], (s.at[c, "majority_share"] - lo) / (hi - lo))
              for c in cantons["canton"]]
    cantons.plot(ax=ax_a, color=colors, edgecolor="white", linewidth=0.6)
    bilingual = cantons[cantons["canton"].isin(languages["bilingual_cantons"])]
    bilingual.boundary.plot(ax=ax_a, color=TEXT_PRIMARY, linewidth=1.6)
    borders.plot(ax=ax_a, color=TEXT_PRIMARY, linewidth=0.9, linestyle=(0, (3, 2)))
    _labels(ax_a, cantons, "canton")
    _frame(ax_a, "(A) Language distribution (BFS)")
    ax_a.legend(handles=[
        Line2D([], [], color=TEXT_PRIMARY, linewidth=1.6,
               label=f"Officially bi- or trilingual canton ({', '.join(languages['bilingual_cantons'])})"),
        Line2D([], [], color=TEXT_PRIMARY, linewidth=0.9, linestyle=(0, (3, 2)),
               label=f"Language border ({areas['label']}, municipalities)")],
        loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=8.5)
    for i, lang in enumerate(languages["majority_of"]):   # one colour scale per language
        cax = fig.add_axes([0.04 + 0.15 * i, 0.135, 0.12, 0.022])
        cmap = ListedColormap([tint(colors_of[lang], t) for t in np.linspace(0, 1, 64)])
        bar = fig.colorbar(plt.cm.ScalarMappable(norm=plt.Normalize(lo, hi), cmap=cmap), cax=cax,
                           orientation="horizontal")
        ticks = np.linspace(lo, hi, 3)
        bar.set_ticks(ticks)
        bar.set_ticklabels([f"{100 * v:g}%" for v in ticks], fontsize=7.5)
        bar.outline.set_visible(False)
        cax.set_title(names[lang], fontsize=8.5, loc="left")

    # (B) coefficient group of every region; Ticino has no group of its own
    regions = cantons.dissolve(by="region").reset_index()[["region", "geometry"]]
    regions["group"] = regions["region"].map(CANTON_LANGUAGE)
    own = regions[regions["group"].notna()]
    own.plot(ax=ax_b, color=own["group"].map(group_color).tolist(), edgecolor="white", linewidth=0.6)
    no_group = regions[regions["group"].isna()]
    handles = [Patch(facecolor=group_color[g], edgecolor="white",
                     label=f"{g} coefficients ({names[languages['group_language'][g]]}; model group "
                           f"{coefficients[g]})") for g in group_color]
    for region in no_group["region"]:
        fill = group_color.get(ticino, EXCLUDED_FILL)
        label = (f"{region}: excluded (no group in the model)" if ticino is None else
                 f"Ticino: no Italian group, uses {ticino} coefficients" if region == "TI" else
                 f"{region}: no group in the model, uses {ticino} coefficients")
        no_group[no_group["region"] == region].plot(ax=ax_b, color=fill, edgecolor="white", linewidth=0.6,
                                                    hatch="///")
        handles.append(Patch(facecolor=fill, edgecolor="white", hatch="///", label=label))
    _labels(ax_b, regions, "region")
    _frame(ax_b, "(B) Assignment in this project")
    ax_b.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.01), frameon=False, fontsize=8.5)

    year = languages["year"]
    fig.text(0.02, 0.075,
             f"(A) Colour: majority among {', '.join(names[k] for k in languages['majority_of'])} as main language "
             f"of the permanent resident population; intensity: its share ({100 * lo:g}–{100 * hi:g}%, several main "
             f"languages per person possible);\nBFS, structural survey {year}, \"Hauptsprachen nach Kanton\". "
             f"Dashed: border between the {areas['label']} (municipalities, status {areas['status']}).\n"
             f"(B) Coefficient group of each of the 23 Calliope regions (AI/AR, BL/BS, NW/OW merged; config "
             f"regions.language, spatial.regional.ticino), choice model {choice_model}.\n"
             f"Boundaries: swisstopo swissBOUNDARIES3D {boundaries_release}, LV95 (EPSG:2056), simplified.",
             fontsize=8, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir, formats)
