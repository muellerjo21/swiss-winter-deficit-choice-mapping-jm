"""Checks against silent failure cases (src/checks.py): a technology without assignment in the attribute mappings,
an empty selection and a missing cost class stop the workflow with a message that names the problem."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from checks import check_technology_mapping, cost_class, require_selection, unmapped_technologies  # noqa: E402

MAPPINGS = {"ownership": (["ccgt", "roof_mounted_pv"], ["battery"]),
            "source": (["ccgt", "roof_mounted_pv"], ["battery", "hydro_reservoir"])}


def test_complete_mapping_passes():
    check_technology_mapping(["ccgt", "roof_mounted_pv", "battery"], {"ownership": MAPPINGS["ownership"]})


def test_excluded_technology_is_no_gap():
    assert unmapped_technologies(["battery", "ccgt"], ["ccgt"], ["battery"]) == []


def test_unmapped_technology_fails_loudly():
    with pytest.raises(ValueError) as error:
        check_technology_mapping(["ccgt", "scgt_natgas", "hydro_reservoir"], MAPPINGS, "scenario.nc")
    message = str(error.value)
    assert "scenario.nc" in message
    assert "ownership: hydro_reservoir, scgt_natgas" in message   # every gap of every mapping is listed
    assert "source: scgt_natgas" in message                       # hydro_reservoir is excluded for source


def test_no_technologies_fails_loudly():
    with pytest.raises(ValueError, match="empty selection"):
        check_technology_mapping([], MAPPINGS, "scenario.nc")


def test_empty_selection_fails_loudly():
    assert require_selection(["a"], "lines") == ["a"]
    with pytest.raises(ValueError, match="no cross-border lines in scenario.nc"):
        require_selection([], "cross-border lines", "scenario.nc")


def test_cost_class():
    assert cost_class(["monetary", "co2"], "monetary") == "monetary"
    with pytest.raises(ValueError, match="monetary"):
        cost_class(["co2"], "monetary")
