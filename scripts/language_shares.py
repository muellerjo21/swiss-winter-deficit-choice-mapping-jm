"""Tidy tables of the BFS language data for the language map (fig12) and its test. Runs in envs/language.yaml.
- Cantons (maps.languages): number of persons per main language and canton, share of the permanent resident
  population (several main languages per person possible, so the shares add up to more than 1), the majority among
  maps.languages.majority_of and its share, and the 95 % confidence interval of each count (± % as published).
  "X" (too few observations, not published) becomes NaN.
- Municipalities (maps.language_areas): language area of every municipality; the code list is read from the export
  itself and matched to the language keys by maps.languages.columns."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(snakemake.scriptdir).parent / "src"))
from config import CANTON_NAME_TO_CODE, region_of_canton


def language_key(label, columns: dict) -> str:
    """Language key whose label start (maps.languages.columns) the label begins with; error if none or several."""
    hits = [key for key, start in columns.items() if str(label).strip().startswith(start)]
    if len(hits) != 1:
        raise ValueError(f"label {label!r} matches {hits} of maps.languages.columns")
    return hits[0]


def canton_code(label: str, aliases: dict) -> str:
    """Canton code of a table label such as "Valais / Wallis" (German name of regions.cantons or an alias)."""
    names = {**CANTON_NAME_TO_CODE, **{name: code for code, name in aliases.items()}}
    hits = {names[part.strip()] for part in str(label).split("/") if part.strip() in names}
    if len(hits) != 1:
        raise ValueError(f"canton label {label!r} matches {sorted(hits)} (regions.cantons, maps.languages.canton_names)")
    return hits.pop()


def canton_shares(path: str, cfg: dict) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=cfg["sheet"], header=None, dtype=object)
    header_row = next(i for i, row in raw.iterrows() if cfg["total_column"] in row.astype(str).str.strip().tolist())
    header = raw.iloc[header_row].astype(str).str.strip()
    total_col = header[header == cfg["total_column"]].index[0]
    lang_cols = {language_key(label, cfg["columns"]): col for col, label in header.items()
                 if col > total_col and pd.notna(label) and label != ""}   # NaN stays NaN in pandas 3
    name_col = total_col - 1
    rows = []
    for _, row in raw.iloc[header_row + 1:].iterrows():
        label = row[name_col]
        if pd.isna(label) or not isinstance(row[total_col], (int, float)):
            continue                                   # header, total row (label in another column) or footnotes
        out = {"canton": canton_code(label, cfg["canton_names"]), "label": str(label).strip(),
               "total": float(row[total_col])}
        for key, col in lang_cols.items():
            count = pd.to_numeric(row[col], errors="coerce")
            out[key] = count
            out[f"share_{key}"] = count / out["total"]
            out[f"ci_pct_{key}"] = pd.to_numeric(row[col + 1], errors="coerce")
        rows.append(out)
    t = pd.DataFrame(rows)
    if sorted(t["canton"]) != sorted(CANTON_NAME_TO_CODE.values()):
        raise ValueError(f"cantons in {path}: {sorted(t['canton'])}")
    majority = t[[f"share_{k}" for k in cfg["majority_of"]]]
    t["majority"] = majority.idxmax(axis=1).str.removeprefix("share_")
    t["majority_share"] = majority.max(axis=1)
    t.insert(1, "region", t["canton"].map(region_of_canton))
    return t


def municipality_areas(path: str, cfg: dict, columns: dict) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    raw = sheets[cfg["sheet"]]
    header_row = next(i for i, row in raw.iterrows()
                      if set(cfg["columns"].values()) <= set(row.astype(str).str.strip()))
    header = raw.iloc[header_row].astype(str).str.strip()
    col = {key: header[header == label].index[0] for key, label in cfg["columns"].items()}
    code_list = str(raw.iloc[header_row + 1, col["area"]]).strip()   # name of the code-list sheet below the header
    codes = sheets[code_list].dropna()
    codes = codes[pd.to_numeric(codes[0], errors="coerce").notna()]
    code_to_language = {int(c): language_key(label, columns) for c, label in zip(codes[0], codes[1])}
    data = raw.iloc[header_row + 2:]
    data = data[pd.to_numeric(data[col["municipality"]], errors="coerce").notna()]
    t = pd.DataFrame({"municipality": data[col["municipality"]].astype(int).to_numpy(),
                      "canton": data[col["canton"]].astype(str).str.strip().to_numpy(),
                      "area_code": data[col["area"]].astype(int).to_numpy()})
    t["language"] = t["area_code"].map(code_to_language)
    if t["language"].isna().any() or t["municipality"].duplicated().any():
        raise ValueError(f"{path}: unknown language-area codes or duplicate municipalities")
    if not set(t["canton"]) <= set(CANTON_NAME_TO_CODE.values()):
        raise ValueError(f"{path}: unknown cantons {sorted(set(t['canton']) - set(CANTON_NAME_TO_CODE.values()))}")
    return t


if __name__ == "__main__":
    p = snakemake.params
    canton_shares(snakemake.input.languages, p.languages).to_csv(snakemake.output.cantons, index=False)
    municipality_areas(snakemake.input.areas, p.areas, p.languages["columns"]).to_csv(
        snakemake.output.municipalities, index=False)
