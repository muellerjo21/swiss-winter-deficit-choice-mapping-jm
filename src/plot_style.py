"""Shared figure style (colours, Matplotlib settings, saving) without heavy dependencies, so that rules in other
conda environments (e.g. the maps in envs/maps.yaml) use the same look as src/make_graphics.py."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

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
