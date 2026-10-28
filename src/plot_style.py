"""Shared figure style (colours, Matplotlib settings, saving) without heavy dependencies, so that rules in other
conda environments (e.g. the maps in envs/maps.yaml) use the same look as src/make_graphics.py."""
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from intervals import credible_interval_label

# Categorical palette (validated colour-blind safe, fixed order) + text/neutral tones
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
NEUTRAL = "#a3a29d"
GRID = "#e4e3df"

# Choice probability of scenario 1 (as in Tröndle et al. 2025): orange (0, scenario 2 preferred) -> beige
# (0.5) -> blue (1, scenario 1 preferred); same orange and blue as SERIES[1] and SERIES[0]
CHOICE_MIDPOINT = "#f3ede2"
CHOICE_CMAP = LinearSegmentedColormap.from_list("choice_probability", [SERIES[1], CHOICE_MIDPOINT, SERIES[0]])
SCENARIO_1_COLOR = SERIES[0]
SCENARIO_2_COLOR = SERIES[1]

# Scenario identity colours, the same in all figures: the highlighted scenarios (config
# figures.highlight_scenarios) get these colours in this order, all other scenarios NEUTRAL. Validated: CVD dE
# >= 9.2, normal-vision dE >= 16.3 (OKLab x 100).
SCENARIO_PALETTE = [SERIES[0], SERIES[1], SERIES[2], SERIES[6]]
# Attribute colours of the contribution figures (fig3, figA1), deliberately disjoint from SCENARIO_PALETTE so
# that a colour never means both a scenario and an attribute: yellow, pink, brown, olive, teal, dark and light grey.
# Validated: CVD dE >= 10.3 within the set; normal-vision dE >= 13.6 (brown/dark grey = Land/Ownership, not
# adjacent in the stack), >= 12.9 to the scenario colours.
ATTRIBUTE_COLORS = ["#f2c14e", "#e87ba4", "#7a4a1e", "#8a8d00", "#0f6e74", "#3b3a37", "#e3e2dd"]

ANALYSIS_LABELS = {
    "regional": "Regional main analysis (22 Calliope regions, TI excluded, population-weighted)",
    "national": "National aggregate (appendix; national attribute values, survey-sample weights)",
}
GROUP_TITLES = {
    "regional": {"national": "Switzerland (population-weighted)", "DE_CH": "German-speaking Switzerland (DE-CH)",
                 "FR_CH": "French-speaking Switzerland (FR-CH)"},
    "national": {"national": "Switzerland (national aggregate)",
                 "DE_CH": "German-speaking Switzerland (DE-CH)", "FR_CH": "French-speaking Switzerland (FR-CH)"},
}


@dataclass(frozen=True)
class FigureSettings:
    """What every figure states and shares: analysis (regional | national), credible interval, price year, the
    scenario order of all figures (first = top/left) with its footnote, and the highlighted scenarios."""
    analysis: str
    credible_interval: float
    interval_type: str
    year: int
    order: tuple = ()
    order_note: str = ""
    highlight: tuple = ()

    def __post_init__(self):
        if self.analysis not in ANALYSIS_LABELS:
            raise ValueError(f"analysis must be one of {list(ANALYSIS_LABELS)}, got {self.analysis!r}")
        if len(self.highlight) > len(SCENARIO_PALETTE):
            raise ValueError(f"at most {len(SCENARIO_PALETTE)} highlighted scenarios, got {len(self.highlight)}")

    @property
    def suffix(self) -> str:
        return f"_{self.analysis}"

    def color(self, scenario: str) -> str:
        return SCENARIO_PALETTE[self.highlight.index(scenario)] if scenario in self.highlight else NEUTRAL

    def interval(self) -> str:
        return credible_interval_label(self.credible_interval, self.interval_type)

    def title(self, group: str) -> str:
        return GROUP_TITLES[self.analysis][group]

    def stamp(self) -> str:
        return f"{ANALYSIS_LABELS[self.analysis]} · {self.interval()} · ElCom prices and EUR/CHF {self.year}."


RC_PARAMS = {
    "font.size": 10.5,
    "axes.titlesize": 12,
    "axes.labelsize": 11.5,
    "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5,
    "legend.fontsize": 10,
    "axes.edgecolor": TEXT_SECONDARY,
    "axes.labelcolor": TEXT_PRIMARY,
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "text.color": TEXT_PRIMARY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "pdf.fonttype": 42,  # embedded TrueType fonts, editable/searchable in the PDF
    "savefig.bbox": "tight",
}
plt.rcParams.update(RC_PARAMS)


def text_color_on(rgba) -> str:
    """Dark text on light fills, white text on saturated fills (relative luminance)."""
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgba[:3])
    return TEXT_PRIMARY if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.3 else "white"


def save(fig, name: str, out_dir, formats=("png", "pdf", "svg")) -> None:
    """One subfolder per format: out_dir/png/name.png, out_dir/pdf/name.pdf, out_dir/svg/name.svg."""
    out_dir = Path(out_dir)
    for fmt in formats:
        (out_dir / fmt).mkdir(parents=True, exist_ok=True)
    # No timestamp in the metadata -> byte-identical files for identical input
    options = {"png": {"dpi": 300}, "pdf": {"metadata": {"CreationDate": None}}, "svg": {"metadata": {"Date": None}}}
    for fmt in formats:
        fig.savefig(out_dir / fmt / f"{name}.{fmt}", **options[fmt])
    plt.close(fig)
