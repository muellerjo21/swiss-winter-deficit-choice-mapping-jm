"""
Thesis-Abbildungen (statisch, Matplotlib) aus data/processed/scenario_attributes_summary.csv und
data/processed/utility_rankings.csv. Speichert jede Abbildung als PNG (300 dpi), PDF und SVG nach graphics/.

Aufruf (aus src/):  python make_graphics.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    PROJECT_ROOT, CHOICE_MODEL_PATH, ATTRIBUTE_COLUMN_TO_MODEL_TERM, SCENARIO_DISPLAY_NAMES,
    LANGUAGE_REGION_WEIGHTS,
)
from load_data import load_beta_partworths_mean, load_beta_partworths_samples
from utility import (
    load_attribute_scale, scale_scenario_attributes, compute_utility_samples, compute_choice_shares,
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GRAPHICS_DIR = PROJECT_ROOT / "graphics"

# Kategoriale Palette (farbenblind-sicher validiert, feste Reihenfolge) + Text-/Neutraltöne
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
NEUTRAL = "#a3a29d"
GRID = "#e4e3df"

REFERENCE_SCENARIO = "baseline"  # nicht in Mellot Table 3

plt.rcParams.update({
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
    "pdf.fonttype": 42,  # eingebettete TrueType-Fonts, im PDF editierbar/durchsuchbar
    "savefig.bbox": "tight",
})


def display_name(scenario_id: str) -> str:
    return SCENARIO_DISPLAY_NAMES.get(scenario_id, scenario_id)


def save(fig, name: str) -> None:
    GRAPHICS_DIR.mkdir(exist_ok=True)
    fig.savefig(GRAPHICS_DIR / f"{name}.png", dpi=300)
    fig.savefig(GRAPHICS_DIR / f"{name}.pdf")
    fig.savefig(GRAPHICS_DIR / f"{name}.svg")
    plt.close(fig)


def load_results() -> tuple[pd.DataFrame, pd.DataFrame]:
    attrs = pd.read_csv(PROCESSED_DIR / "scenario_attributes_summary.csv")
    rankings = pd.read_csv(PROCESSED_DIR / "utility_rankings.csv")
    return attrs, rankings


# ---------------------------------------------------------------------------
# 1. Choice-Modell-Rang vs. Mellot-Kostenrang
# ---------------------------------------------------------------------------
def fig_rank_vs_cost(rankings: pd.DataFrame) -> None:
    df = rankings[rankings["scenario_id"] != REFERENCE_SCENARIO].copy()
    df["diff"] = df["rank_national"] - df["rank_mellot_cost"]

    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    n = int(df[["rank_national", "rank_mellot_cost"]].max().max())
    ax.plot([0.5, n + 0.5], [0.5, n + 0.5], ls="--", lw=1, color=NEUTRAL, zorder=1)

    # Farbe = Richtung der Abweichung (gleiche Codierung wie Abb. 4)
    colors = np.where(df["diff"] < 0, SERIES[0], np.where(df["diff"] > 0, SERIES[1], NEUTRAL))
    ax.scatter(df["rank_mellot_cost"], df["rank_national"], s=70, c=colors,
               edgecolors="white", linewidths=1.5, zorder=3)

    # Direkte Labels; S/CCGT-Paar teilt den Kostenrang -> Labels versetzt
    offsets = {
        "policy_sccgt_no_h2": (8, 4, "left"),
        "policy_sccgt_plus_h2": (8, -4, "left"),
        "baseline_no_self_sufficiency_result_4H": (8, 0, "left"),
        "policy_wind_x2": (-8, 0, "right"),
        "policy_h2_imports_only": (8, 0, "left"),
        "policy_chp": (8, 0, "left"),
        "policy_roof_pv": (-8, 0, "right"),
    }
    for _, r in df.iterrows():
        dx, dy, ha = offsets.get(r["scenario_id"], (8, 0, "left"))
        highlight = abs(r["diff"]) >= 2
        label = display_name(r["scenario_id"])
        if highlight:
            label += f"  ({'+' if r['diff'] > 0 else '−'}{abs(int(r['diff']))})"
        ax.annotate(label, (r["rank_mellot_cost"], r["rank_national"]), xytext=(dx, dy),
                    textcoords="offset points", ha=ha, va="center",
                    fontsize=10 if highlight else 9.5,
                    fontweight="bold" if highlight else "normal",
                    color=TEXT_PRIMARY if highlight else TEXT_SECONDARY)

    ax.set_xlim(0.5, n + 0.5)
    ax.set_ylim(n + 0.5, 0.5)  # Rang 1 oben
    ax.set_xticks(range(1, n + 1))
    ax.set_yticks(range(1, n + 1))
    ax.set_xlabel("Cost rank, Mellot et al. (2024) Table 3 (1 = cheapest)")
    ax.set_ylabel("Predicted preference rank, choice model, CH (1 = most preferred)")

    handles = [
        plt.Line2D([], [], marker="o", ls="", color=SERIES[0], markersize=8, label="Preferred more than cost suggests"),
        plt.Line2D([], [], marker="o", ls="", color=SERIES[1], markersize=8, label="Preferred less than cost suggests"),
        plt.Line2D([], [], marker="o", ls="", color=NEUTRAL, markersize=8, label="Same rank"),
        plt.Line2D([], [], ls="--", lw=1, color=NEUTRAL, label="Identical rank (diagonal)"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=2, frameon=False)
    fig.text(0, -0.13, f"Rank difference in brackets for |Δ| ≥ 2. Not shown: {display_name(REFERENCE_SCENARIO)} "
             "(not in Mellot Table 3; choice-model rank 12).", fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    save(fig, "fig1_rank_choice_vs_cost")


# ---------------------------------------------------------------------------
# 2. Forest Plot: Utility mit 94%-Credible-Interval
# ---------------------------------------------------------------------------
def fig_forest(rankings: pd.DataFrame) -> None:
    panels = [("DE_CH", "German-speaking Switzerland (DE-CH)"),
              ("FR_CH", "French-speaking Switzerland (FR-CH)"),
              ("national", "Switzerland, population-weighted")]
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 11), sharex=True)
    for ax, (tag, title) in zip(axes, panels):
        col = f"utility_{tag}"
        df = rankings.sort_values(col, ascending=True).reset_index(drop=True)  # höchste oben
        y = np.arange(len(df))
        is_ref = (df["scenario_id"] == REFERENCE_SCENARIO).values
        color = np.where(is_ref, TEXT_SECONDARY, SERIES[0])
        for yi, (_, r), c in zip(y, df.iterrows(), color):
            ax.plot([r[f"{col}_ci94_low"], r[f"{col}_ci94_high"]], [yi, yi], color=c, lw=2, solid_capstyle="round")
            if c == TEXT_SECONDARY:  # Referenzszenario: offener Marker
                ax.plot(r[col], yi, "o", color=c, markersize=7, mfc="white", mec=c, markeredgewidth=1.8)
            else:
                ax.plot(r[col], yi, "o", color=c, markersize=7, markeredgecolor="white", markeredgewidth=1.5)
        ax.set_yticks(y)
        ax.set_yticklabels([display_name(s) for s in df["scenario_id"]])
        for lbl, ref in zip(ax.get_yticklabels(), is_ref):
            if ref:
                lbl.set_color(TEXT_SECONDARY); lbl.set_fontstyle("italic")
        ax.set_ylim(-0.6, len(df) - 0.4)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[-1].set_xlabel("Utility (posterior mean, 94% credible interval)")
    fig.text(0, -0.01, "Credible intervals reflect posterior uncertainty of the choice-model coefficients only. "
             f"Open marker: {display_name(REFERENCE_SCENARIO)}.", fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout(h_pad=1.8)
    save(fig, "fig2_utility_forest")


# ---------------------------------------------------------------------------
# 3. Attribut-Beitragszerlegung (divergierend gestapelt)
# ---------------------------------------------------------------------------
CONTRIBUTION_GROUPS = [  # (Label, Modell-Terme); Reihenfolge = Farbslot-Reihenfolge
    ("Cost", ["cost"]),
    ("Import", ["import"]),
    ("Land", ["land"]),
    ("Wind share", ["source_wind"]),
    ("Gas share", ["source_gas"]),
    ("Ownership", ["ownership_commercial", "ownership_community"]),
    ("Other (biomass, coal, nuclear, transmission)", ["source_biomass", "source_coal", "source_nuclear", "transmission"]),
]


def compute_contributions(attrs: pd.DataFrame, region: str, scale: dict) -> pd.DataFrame:
    """beta_mean * x_scaled pro Szenario und Beitragsgruppe."""
    beta = load_beta_partworths_mean(CHOICE_MODEL_PATH, country=region).set_index("attribute")["beta_mean"]
    rows = {}
    for _, r in attrs.iterrows():
        per_term = scale_scenario_attributes(r, scale) * beta.loc[list(ATTRIBUTE_COLUMN_TO_MODEL_TERM.values())]
        rows[r["scenario_id"]] = {label: per_term[terms].sum() for label, terms in CONTRIBUTION_GROUPS}
    return pd.DataFrame(rows).T


def fig_contributions(attrs: pd.DataFrame, rankings: pd.DataFrame) -> None:
    scale = load_attribute_scale(CHOICE_MODEL_PATH)
    order = rankings.sort_values("utility_national", ascending=True)["scenario_id"].tolist()  # beste oben
    regions = [("DE-CH", "DE-CH"), ("FR-CH", "FR-CH")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.2), sharey=True)
    for ax, (region, title) in zip(axes, regions):
        contrib = compute_contributions(attrs, region, scale).loc[order]
        y = np.arange(len(order))
        pos = np.zeros(len(order)); neg = np.zeros(len(order))
        for (label, _), color in zip(CONTRIBUTION_GROUPS, SERIES):
            v = contrib[label].values
            left = np.where(v >= 0, pos, neg)
            ax.barh(y, v, left=left, height=0.7, color=color, edgecolor="white", linewidth=1, label=label)
            pos += np.clip(v, 0, None); neg += np.clip(v, None, 0)
        total = contrib.sum(axis=1).values
        ax.plot(total, y, "D", color=TEXT_PRIMARY, markersize=5.5, markeredgecolor="white",
                markeredgewidth=1, label="Total utility", zorder=4)
        ax.axvline(0, color=TEXT_SECONDARY, lw=1)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_xlabel("Contribution to utility (β × scaled attribute)")
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(np.arange(len(order)))
    axes[0].set_yticklabels([display_name(s) for s in order])
    lo = min(a.get_xlim()[0] for a in axes); hi = max(a.get_xlim()[1] for a in axes)
    for a in axes:
        a.set_xlim(lo, hi)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.55, 1.08))
    fig.text(0, -0.02, "Scenarios sorted by national utility (highest at top). Positive contributions to the right "
             "of zero, negative to the left.\nA negative cost change (price decrease vs. ElCom 2025) contributes "
             "positively.", fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout()
    save(fig, "fig3_utility_contributions")


# ---------------------------------------------------------------------------
# 4. Slope-Chart DE-CH vs. FR-CH
# ---------------------------------------------------------------------------
def fig_slope_regions(rankings: pd.DataFrame) -> None:
    df = rankings.copy()
    fig, ax = plt.subplots(figsize=(6.5, 6.2))
    for _, r in df.iterrows():
        a, b = r["rank_DE_CH"], r["rank_FR_CH"]
        changed = a != b
        color = SERIES[0] if b < a else SERIES[1] if b > a else NEUTRAL
        lw, z = (2.2, 3) if changed else (1.2, 2)
        ax.plot([0, 1], [a, b], color=color, lw=lw, zorder=z, solid_capstyle="round")
        for x, rank in [(0, a), (1, b)]:
            ax.plot(x, rank, "o", color=color, markersize=7, markeredgecolor="white", markeredgewidth=1.5, zorder=z + 1)
        name = display_name(r["scenario_id"])
        style = dict(fontsize=10, va="center", color=TEXT_PRIMARY if changed else TEXT_SECONDARY,
                     fontweight="bold" if changed else "normal")
        ax.text(-0.05, a, f"{name}  {int(a)}", ha="right", **style)
        ax.text(1.05, b, f"{int(b)}  {name}", ha="left", **style)
    n = int(df[["rank_DE_CH", "rank_FR_CH"]].max().max())
    ax.set_ylim(n + 0.6, 0.4)
    ax.set_xlim(-0.05, 1.05)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Rank DE-CH", "Rank FR-CH"], fontsize=11.5, color=TEXT_PRIMARY)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.xaxis.set_ticks_position("top")
    ax.set_yticks([])
    for s in ["left", "bottom"]:
        ax.spines[s].set_visible(False)
    handles = [
        plt.Line2D([], [], color=SERIES[0], lw=2.2, label="Higher rank in FR-CH"),
        plt.Line2D([], [], color=SERIES[1], lw=2.2, label="Lower rank in FR-CH"),
        plt.Line2D([], [], color=NEUTRAL, lw=1.2, label="Same rank"),
    ]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False)
    save(fig, "fig4_rank_de_vs_fr")


# ---------------------------------------------------------------------------
# 5. Kosten vs. vorhergesagte Präferenz (aktualisierte Version von cost_vs_preference.png)
# ---------------------------------------------------------------------------
def fig_cost_vs_preference(attrs: pd.DataFrame) -> None:
    """Oben: Mellot-Kostenänderung ggü. EP2050+; unten: Softmax-Choice-Share (national) über die
    11 Szenarien aus Mellot Table 3, mit 94%-Credible-Interval aus den Posterior-Samples."""
    df = attrs.dropna(subset=["mellot_cost_change_pct"]).sort_values("mellot_cost_change_pct").reset_index(drop=True)
    scale = load_attribute_scale(CHOICE_MODEL_PATH)
    national = 0
    for region, w in LANGUAGE_REGION_WEIGHTS.items():
        beta_samples = load_beta_partworths_samples(CHOICE_MODEL_PATH, country=region)
        national = national + w * np.stack([compute_utility_samples(r, beta_samples, scale) for _, r in df.iterrows()])
    shares = compute_choice_shares(dict(zip(df["scenario_id"], national)))
    share = np.array([100 * shares[s].mean() for s in df["scenario_id"]])
    lo = np.array([100 * np.quantile(shares[s], 0.03) for s in df["scenario_id"]])
    hi = np.array([100 * np.quantile(shares[s], 0.97) for s in df["scenario_id"]])

    x = np.arange(len(df))
    fig, (ax_cost, ax_pref) = plt.subplots(2, 1, figsize=(6.5, 6.8), sharex=True, height_ratios=[1, 1.15])
    ax_cost.bar(x, df["mellot_cost_change_pct"], width=0.7, color=NEUTRAL, edgecolor="white", linewidth=1)
    ax_cost.axhline(0, color=TEXT_SECONDARY, lw=1)
    ax_cost.set_ylabel("System cost change\nvs. EP2050+ (%)")
    ax_cost.set_title("Cost (Mellot et al. 2024, Table 3)", loc="left", fontweight="bold")

    ax_pref.bar(x, share, width=0.7, color=SERIES[0], edgecolor="white", linewidth=1)
    ax_pref.errorbar(x, share, yerr=[share - lo, hi - share], fmt="none", ecolor=TEXT_PRIMARY, elinewidth=1.2, capsize=3)
    uniform = 100 / len(df)
    ax_pref.axhline(uniform, ls="--", lw=1, color=TEXT_SECONDARY)
    ax_pref.text(len(df) - 0.45, uniform, f"equal share ({uniform:.1f}%)", ha="right", va="bottom",
                 fontsize=9, color=TEXT_SECONDARY)
    ax_pref.set_ylabel("Predicted choice share,\nCH population-weighted (%)")
    ax_pref.set_title("Predicted citizen preference (choice model)", loc="left", fontweight="bold")
    ax_pref.set_ylim(0, max(hi) * 1.15)
    ax_pref.set_xticks(x)
    ax_pref.set_xticklabels([display_name(s) for s in df["scenario_id"]], rotation=45, ha="right", rotation_mode="anchor")
    for ax in (ax_cost, ax_pref):
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
    fig.text(0, -0.03, "Scenarios sorted by system cost (cheapest left). Choice shares: multinomial logit over the 11 "
             "scenarios (IIA assumption),\nbars = posterior mean, whiskers = 94% credible interval.",
             fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout(h_pad=1.5)
    save(fig, "fig5_cost_vs_preference")


if __name__ == "__main__":
    attrs, rankings = load_results()
    fig_rank_vs_cost(rankings)
    fig_forest(rankings)
    fig_contributions(attrs, rankings)
    fig_slope_regions(rankings)
    fig_cost_vs_preference(attrs)
    print(f"Saved graphics to {GRAPHICS_DIR}")
