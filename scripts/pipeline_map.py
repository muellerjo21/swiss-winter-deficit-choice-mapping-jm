"""Interactive pipeline map (build/pipeline_map.html): the graph of `snakemake --rulegraph` drawn by graphviz as in
`snakemake dag`, simplified (no arrows into test and all, no detours via `tred`; the panel lists all direct
dependencies), once for all rules and once for the regional main analysis; the texts of docs/pipeline_map.yaml and the page docs/pipeline_map_template.html. The numbers in
the texts are read from the results (values); the build fails if a rule has no text, a text names a rule that does not
exist, or a text uses an unknown {placeholder}, so the map cannot drift from the workflow."""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import SCENARIO_DISPLAY_NAMES

LAST = ["test", "all"]  # bottom row of the map
LAND_DEFINITIONS = {"national_share": "Landnutzung geteilt durch die Fläche der Schweiz",
                    "canton_mean": "Mittel der Kantonsanteile"}


def name(scenario_id: str) -> str:
    return SCENARIO_DISPLAY_NAMES.get(scenario_id, scenario_id)


def fixed(value: float, decimals: int = 2) -> str:
    """Rounded half up (28.965 -> 28.97); minus sign as typographic minus."""
    text = str(Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))
    return text.replace("-", "−")


def join(items: list) -> str:
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " und " + items[-1]


def read_rulegraph(path: str) -> tuple[dict, list]:
    """{graphviz node id: rule name} and the edges (producer, consumer) by rule name."""
    text = Path(path).read_text()
    names = dict(re.findall(r'^\s*(\d+)\[label = "([^"]+)"', text, re.M))
    edges = sorted({(names[a], names[b]) for a, b in re.findall(r"^\s*(\d+) -> (\d+)", text, re.M)})
    return names, [list(e) for e in edges]


def survey_values(path_to_choice_model: str) -> tuple[list, float]:
    """Import levels shown in the survey and the share of Swiss respondents (DE-CH, FR-CH) with m = 1."""
    idata = az.from_netcdf(path_to_choice_model)
    cd = idata.constant_data
    levels = np.unique(np.round(np.concatenate([cd["attribute_values_left"].sel(attribute="import").values,
                                                cd["attribute_values_right"].sel(attribute="import").values]), 6))
    countries = list(idata.posterior["beta_partworths"]["country"].values)
    swiss = [countries.index(c) for c in ("DE-CH", "FR-CH")]
    resp = pd.DataFrame({"r": cd["r"].values, "c": cd["c"].values, "m": cd["m"].values})
    resp = resp[resp["c"].isin(swiss)].groupby("r")["m"].max()
    return [float(v) for v in levels], float(resp.mean())


def values(inp, p) -> dict:
    """Every {placeholder} of docs/pipeline_map.yaml, computed from the results and the config."""
    elcom = json.loads(Path(inp.elcom_national).read_text())
    eur_chf = json.loads(Path(inp.eur_chf).read_text())["eur_to_chf"]
    regions = pd.read_csv(inp.elcom_regions).set_index("region")["total_rp_kwh"]
    population = pd.read_csv(inp.population).set_index("region")["population"]
    excluded = [r for r in p.exclude if r in population.index]
    base = pd.read_csv(inp.base_years)
    leaders = base[(base["region"] == "national") & (base["rank"] == 1)].sort_values("year")
    by_leader = {}
    for _, r in leaders.iterrows():
        by_leader.setdefault(r["scenario_id"], []).append(int(r["year"]))
    switch = pd.read_csv(inp.switches_regional).set_index("region").loc["national"]
    imports = pd.read_csv(inp.import_shares).set_index("scenario_id")
    levels, mobile_share = survey_values(inp.choice_model)
    unclipped = imports["import_share_electricity_unclipped"]
    exporters = [(name(s), v) for s, v in unclipped.items() if v < 0]
    matrix = pd.read_csv(inp.pairwise_matrix)
    report = Path(p.test_report).read_text()
    tests = re.search(r"(\d+) tests? took", report)
    if not tests:
        raise ValueError(f"no test count in {p.test_report}")
    interval = (f"{p.credible_interval * 100:g}-%-HDI" if p.interval_type == "hdi"
                else f"{p.credible_interval * 100:g}-%-Intervall (equal-tailed)")
    years = sorted(set(p.base_years) | {p.price_year})
    return {
        "price_year": p.price_year,
        "price_category": p.price_category,
        "price_years": f"{years[0]} bis {years[-1]}",
        "ref_price_national": fixed(elcom["total_rp_kwh"]),
        "base_year_leaders": "; ".join(f"mit {join(y)} {name(s)}" for s, y in by_leader.items()),
        "eur_chf": fixed(eur_chf, 4),
        "population_date": f"31.12.{p.population_year}",
        "n_regions": len(population),
        "n_included": len(population) - len(excluded),
        "excluded": join(excluded),
        "excluded_share": f"{fixed(100 * population[excluded].sum() / population.sum(), 1)} %",
        "ref_price_regional_range": f"{fixed(regions.min())} Rp./kWh in {regions.idxmin()} bis {fixed(regions.max())} "
                                    f"in {regions.idxmax()}",
        "boundaries_release": "Release " + re.search(r"swissboundaries3d_(\d{4}-\d{2})", p.boundaries_url).group(1),
        "land_definition": LAND_DEFINITIONS[p.land_definition],
        "n_scenarios": len(pd.read_csv(inp.attributes)),
        "import_definition": p.import_definition,
        "survey_import_levels": join([f"{v:g}" for v in levels]),
        "survey_import_min": f"{levels[0]:g}",
        "n_import_below": int((unclipped < levels[0]).sum()),
        "net_export_note": (f"{join([n for n, _ in exporters])} "
                            f"{'exportiert' if len(exporters) == 1 else 'exportieren'} netto "
                            f"({join([fixed(100 * v, 1) + ' %' for _, v in exporters])}), "
                            "der Anteil wird auf 0 gesetzt." if exporters else "kein Szenario exportiert netto."),
        "interval": interval,
        "curve_range": f"{p.curve_start:g} bis {p.curve_stop:g}",
        "mobile_sample_share": fixed(mobile_share, 3),
        "switch_shift": fixed(switch["switch_shift_rp_kwh"], 1),
        "switch_pair": f"{name(switch['scenario_before'])} → {name(switch['scenario_after'])}",
        "n_pairs": int((matrix["scenario_1"] != matrix["scenario_2"]).sum()),
        "test_count": int(tests.group(1)),
        "n_map_pairs": len(p.map_pairs),
        "map_range": "{:g} bis {:g} %".format(*p.map_range),
        "map_range_variant": "{:g} bis {:g} %".format(*p.map_range_variant),
    }


def fill(text: str, vals: dict, where: str) -> str:
    unknown = sorted(set(re.findall(r"\{(\w+)\}", text)) - set(vals))
    if unknown:
        raise ValueError(f"unknown placeholders {unknown} in {where}")
    return text.format_map(vals)


def check_texts(rules: list, texts: dict) -> dict:
    described = texts["rules"]
    missing, stale = sorted(set(rules) - set(described)), sorted(set(described) - set(rules))
    if missing or stale:
        raise ValueError(f"docs/pipeline_map.yaml out of date: rules without text {missing}, texts without rule {stale}")
    unknown = sorted({v["group"] for v in described.values()} - set(texts["groups"]))
    if unknown:
        raise ValueError(f"unknown groups in docs/pipeline_map.yaml: {unknown}")
    return described


def write_dot(rules: list, edges: list, path: str) -> None:
    """Graph for graphviz (the page shows it after `tred`, i.e. without detours): the rules and their edges without
    those into test and all; test and all as the bottom row, the last steps invisibly linked to test for the layout."""
    body = [(a, b) for a, b in edges if a in rules and b in rules and b not in LAST]
    sinks = [r for r in rules if r not in LAST and not any(a == r for a, _ in body)]
    lines = ["digraph pipeline {", "  graph[rankdir=TB, nodesep=0.35, ranksep=0.55, bgcolor=white];",
             "  node[shape=box, style=rounded, fontname=Helvetica, fontsize=10, penwidth=2];",
             "  edge[penwidth=1.4, color=grey];"]
    lines += [f'  "{r}";' for r in rules if r not in LAST]
    lines += [f'  "{a}" -> "{b}";' for a, b in body]
    lines += ['  { rank=sink; "test"; "all"; }', '  "test" -> "all";']
    lines += [f'  "{r}" -> "test" [style=invis];' for r in sinks]
    Path(path).write_text("\n".join(lines + ["}"]) + "\n")


def dots(inp, out) -> None:
    """Two graphs: all rules, and the regional main analysis without the national aggregate."""
    names, edges = read_rulegraph(inp.rulegraph)
    rules = sorted(names.values())
    described = check_texts(rules, yaml.safe_load(Path(inp.texts).read_text()))
    write_dot(rules, edges, out.full)
    write_dot([r for r in rules if not described[r].get("national", False)], edges, out.regional)


def svg_body(path: str, svg_id: str) -> str:
    """graphviz SVG without XML header, scaled by the page."""
    svg = Path(path).read_text()
    svg = svg[svg.index("<svg"):]
    return re.sub(r'<svg width="[^"]*" height="[^"]*"', f'<svg id="{svg_id}" class="graph-svg" role="group" '
                  'aria-label="Pipeline-Graph"', svg, 1)


def build(inp, p, path_to_output: str) -> None:
    names, edges = read_rulegraph(inp.rulegraph)
    rules = sorted(names.values())
    texts = yaml.safe_load(Path(inp.texts).read_text())
    described = check_texts(rules, texts)
    vals = values(inp, p)
    nodes = {r: {"g": described[r]["group"], "nat": bool(described[r].get("national", False)),
                 "text": fill(described[r]["text"], vals, r),
                 "open": fill(described[r].get("open", ""), vals, r)} for r in rules}
    data = {"groups": texts["groups"], "startHint": fill(texts["start_hint"], vals, "start_hint"),
            "nodes": nodes, "edges": edges}
    page = Path(inp.template).read_text()
    for marker in ("/*PIPELINE_DATA*/", "<!--PIPELINE_SVG_FULL-->", "<!--PIPELINE_SVG_REGIONAL-->"):
        if marker not in page:
            raise ValueError(f"template has no {marker} placeholder")
    page = page.replace("/*PIPELINE_DATA*/", json.dumps(data, ensure_ascii=False, indent=1))
    page = page.replace("<!--PIPELINE_SVG_FULL-->", svg_body(inp.graph_full, "svg-full"))
    Path(path_to_output).write_text(page.replace("<!--PIPELINE_SVG_REGIONAL-->", svg_body(inp.graph_regional, "svg-regional")))


if __name__ == "__main__":
    if snakemake.rule == "pipeline_map_dot":
        dots(snakemake.input, snakemake.output)
    else:
        build(snakemake.input, snakemake.params, snakemake.output[0])
