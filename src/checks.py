"""Checks that turn silent failure cases into errors (standard library only, so that the tests can import them):

- technology mappings of the choice-model attributes: every technology that can produce electricity at a Swiss
  location must be in each mapping (ownership, source) or in that mapping's list of excluded technologies; otherwise
  the technology would drop out of the shares without notice (as happened with the gas turbines scgt_natgas and
  scgt_renewable);
- empty selections: a selection that must not be empty (e.g. the cross-border lines of the import attribute) stops
  the workflow instead of giving 0;
- cost class: the costs of the result files must contain the configured class (no fallback to another class).
"""


def unmapped_technologies(technologies, mapped, excluded) -> list:
    """Technologies that are neither mapped nor excluded, sorted."""
    return sorted(set(technologies) - set(mapped) - set(excluded))


def check_technology_mapping(technologies, mappings: dict, source: str = "") -> None:
    """mappings: name -> (mapped technologies, excluded technologies). Raises ValueError if `technologies` is empty
    or if any technology has no assignment; the message lists every gap per mapping and names source (the file)."""
    where = f" in {source}" if source else ""
    require_selection(technologies, "electricity-producing technologies at the Swiss locations", source)
    gaps = {name: unmapped_technologies(technologies, mapped, excluded) for name, (mapped, excluded) in mappings.items()}
    gaps = {name: techs for name, techs in gaps.items() if techs}
    if gaps:
        detail = "; ".join(f"{name}: {', '.join(techs)}" for name, techs in gaps.items())
        raise ValueError(f"electricity-producing technologies without assignment{where}: {detail}. Add each to the "
                         "mapping or to its list of excluded technologies (config/default.yaml, section attributes).")


def require_selection(items, what: str, source: str = ""):
    """items unchanged if not empty; ValueError naming what was selected (and the file) otherwise."""
    if len(items) == 0:
        raise ValueError(f"empty selection: no {what}{f' in {source}' if source else ''}")
    return items


def cost_class(classes, required: str) -> str:
    """The cost class of the price formula (calliope.cost_class); ValueError if the result file does not have it."""
    classes = [str(c) for c in classes]
    if required not in classes:
        raise ValueError(f"cost class {required!r} not in the result file (classes: {classes})")
    return required
