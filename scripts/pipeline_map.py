"""Interactive pipeline map (build/pipeline_map.html): arrows from `snakemake --rulegraph`, texts from
docs/pipeline_map.yaml, page from docs/pipeline_map_template.html. Fails if a rule of the workflow has no text or the
texts name a rule that does not exist, so the map cannot drift from the workflow."""
import json
import re
from pathlib import Path

import yaml

LAST = ["test", "all"]  # always the two bottom rows


def read_rulegraph(path: str) -> tuple[list, list]:
    text = Path(path).read_text()
    names = dict(re.findall(r'^\s*(\d+)\[label = "([^"]+)"', text, re.M))
    edges = sorted({(names[a], names[b]) for a, b in re.findall(r"^\s*(\d+) -> (\d+)", text, re.M)})
    return sorted(names.values()), [list(e) for e in edges]


def layers(rules: list, edges: list, min_layer: dict) -> dict:
    """Row of every rule: longest path from the raw data (or min_layer if higher); test and all at the bottom."""
    parents = {r: [a for a, b in edges if b == r] for r in rules}
    row = {}

    def depth(r):
        if r not in row:
            row[r] = max([min_layer.get(r, 0)] + [depth(p) + 1 for p in parents[r]])
        return row[r]

    for r in rules:
        depth(r)
    body = max(row[r] for r in rules if r not in LAST)
    for i, r in enumerate(LAST):
        if r in row:
            row[r] = body + 1 + i
    return row


def build(path_to_rulegraph: str, path_to_texts: str, path_to_template: str, path_to_output: str) -> None:
    rules, edges = read_rulegraph(path_to_rulegraph)
    texts = yaml.safe_load(Path(path_to_texts).read_text())
    described = texts["rules"]
    missing, stale = sorted(set(rules) - set(described)), sorted(set(described) - set(rules))
    if missing or stale:
        raise ValueError(f"docs/pipeline_map.yaml out of date: rules without text {missing}, texts without rule {stale}")
    unknown = sorted({v["group"] for v in described.values()} - set(texts["groups"]))
    if unknown:
        raise ValueError(f"unknown groups in docs/pipeline_map.yaml: {unknown}")
    row = layers(rules, edges, {r: v["min_layer"] for r, v in described.items() if "min_layer" in v})
    order = list(described)  # order within a row as in the YAML file
    nodes = [{"id": r, "g": described[r]["group"], "layer": row[r], "text": described[r]["text"],
              "ask": described[r].get("ask", ""), "nat": bool(described[r].get("national", False))}
             for r in sorted(rules, key=order.index)]
    data = {"groups": texts["groups"], "layerLabels": texts["layer_labels"], "startHint": texts["start_hint"],
            "nodes": nodes, "edges": edges}
    page = Path(path_to_template).read_text()
    if "/*PIPELINE_DATA*/" not in page:
        raise ValueError("template has no /*PIPELINE_DATA*/ placeholder")
    Path(path_to_output).write_text(page.replace("/*PIPELINE_DATA*/", json.dumps(data, ensure_ascii=False, indent=1)))


if __name__ == "__main__":
    build(snakemake.input.rulegraph, snakemake.input.texts, snakemake.input.template, snakemake.output[0])
