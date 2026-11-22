"""Helper functions of the Snakefile (included before the rules)."""
import re
import sys
from pathlib import Path


def numbers_from_text(value):
    """--config passes values inside nested dicts as text ("0.5"); turn numeric text back into numbers, recursively
    (values from config/default.yaml are numbers already and stay unchanged)."""
    if isinstance(value, dict):
        return {k: numbers_from_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [numbers_from_text(v) for v in value]
    if isinstance(value, str) and re.fullmatch(r"-?\d+(\.\d*)?([eE][-+]?\d+)?", value.strip()):
        return int(value) if re.fullmatch(r"-?\d+", value.strip()) else float(value)
    return value


def src_modules(*scripts):
    """src/*.py modules that the given scripts import, directly or through other src modules. They are inputs of the
    rules, so that a change of the code re-runs the rules that use it. Not used for the fetch rules: a code change
    should not repeat a download (re-fetch on purpose with --forcerun <rule>)."""
    available = {p.stem: p for p in Path("src").glob("*.py")}
    found, todo = set(), [Path(s) for s in scripts]
    while todo:
        text = todo.pop().read_text()
        for name in re.findall(r"^\s*(?:from|import)\s+(\w+)", text, re.M):
            if name in available and name not in found:
                found.add(name)
                todo.append(available[name])
    return sorted(str(available[name]) for name in found)


def scenario_files(year):
    """Scenario ID -> result file of the weather year; scenarios without a run for that year are skipped."""
    files = {s: f.get(year) or f.get(str(year)) for s, f in config["scenarios"].items()}
    missing = [s for s, f in files.items() if not f]
    if missing:
        print(f"Weather year {year}: no result file for {', '.join(missing)}; skipped.", file=sys.stderr)
    return {s: f for s, f in files.items() if f}


def scenario_dir(year):
    return Path(config["data"]["scenario_dir"].format(weather_year=year))
