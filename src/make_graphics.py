"""
Thesis figures (static, Matplotlib). National aggregate (make_all): from scenario_attributes_summary.csv and
utility_rankings.csv; regional main analysis (make_all_regional, suffix _regional): from the regional results.
Saves each figure as PNG (300 dpi), PDF and SVG.

Usage (from src/):  python make_graphics.py
"""

import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from config import (
    PROJECT_ROOT, CHOICE_MODEL_PATH, ATTRIBUTE_COLUMN_TO_MODEL_TERM, SCENARIO_DISPLAY_NAMES,
    LANGUAGE_REGION_WEIGHTS, CREDIBLE_INTERVAL, CANTON_LANGUAGE,
)
from load_data import (
    load_beta_partworths_mean, load_beta_partworths_samples,
    load_mobile_partworths_mean, load_mobile_partworths_samples,
)
from utility import (
    load_attribute_scale, raw_attributes, to_real_units, compute_utility_samples, compute_choice_shares,
    credible_interval_quantiles, credible_interval_tag,
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GRAPHICS_DIR = PROJECT_ROOT / "graphics"

from plot_style import (  # colours, Matplotlib settings and save() shared with the map figures
    SERIES, TEXT_PRIMARY, TEXT_SECONDARY, NEUTRAL, GRID, CHOICE_CMAP, SCENARIO_1_COLOR, SCENARIO_2_COLOR, save,
    text_color_on,
)

REFERENCE_SCENARIO = "baseline"  # not in Mellot Table 3


def display_name(scenario_id: str) -> str:
    return SCENARIO_DISPLAY_NAMES.get(scenario_id, scenario_id)


def load_results(attrs_path: Path = PROCESSED_DIR / "scenario_attributes_summary.csv",
                 rankings_path: Path = PROCESSED_DIR / "utility_rankings.csv") -> tuple[pd.DataFrame, pd.DataFrame]:
    attrs = pd.read_csv(attrs_path)
    rankings = pd.read_csv(rankings_path)
    return attrs, rankings


# ---------------------------------------------------------------------------
# 1. Choice-model rank vs. Mellot cost rank
# ---------------------------------------------------------------------------
def fig_rank_vs_cost(rankings: pd.DataFrame, out_dir: Path = GRAPHICS_DIR, name: str = "fig1_rank_choice_vs_cost") -> None:
    df = rankings[rankings["scenario_id"] != REFERENCE_SCENARIO].copy()
    df["diff"] = df["rank_national"] - df["rank_mellot_cost"]

    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    n = int(df[["rank_national", "rank_mellot_cost"]].max().max())
    ax.plot([0.5, n + 0.5], [0.5, n + 0.5], ls="--", lw=1, color=NEUTRAL, zorder=1)

    # Colour = direction of the deviation (same encoding as Fig. 4)
    colors = np.where(df["diff"] < 0, SERIES[0], np.where(df["diff"] > 0, SERIES[1], NEUTRAL))
    ax.scatter(df["rank_mellot_cost"], df["rank_national"], s=70, c=colors,
               edgecolors="white", linewidths=1.5, zorder=3)

    # Direct labels; the S/CCGT pair shares a cost rank -> labels offset
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
    ax.set_ylim(n + 0.5, 0.5)  # rank 1 at the top
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
    save(fig, name, out_dir)


# ---------------------------------------------------------------------------
# 2. Forest plot: utility with credible interval (utility.credible_interval)
# ---------------------------------------------------------------------------
def fig_forest(rankings: pd.DataFrame, out_dir: Path = GRAPHICS_DIR,
               credible_interval: float = CREDIBLE_INTERVAL, name: str = "fig2_utility_forest") -> None:
    ci_tag = credible_interval_tag(credible_interval)
    panels = [("DE_CH", "German-speaking Switzerland (DE-CH)"),
              ("FR_CH", "French-speaking Switzerland (FR-CH)"),
              ("national", "Switzerland, population-weighted")]
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 11), sharex=True)
    for ax, (tag, title) in zip(axes, panels):
        col = f"utility_{tag}"
        df = rankings.sort_values(col, ascending=True).reset_index(drop=True)  # highest at the top
        y = np.arange(len(df))
        is_ref = (df["scenario_id"] == REFERENCE_SCENARIO).values
        color = np.where(is_ref, TEXT_SECONDARY, SERIES[0])
        for yi, (_, r), c in zip(y, df.iterrows(), color):
            ax.plot([r[f"{col}_{ci_tag}_low"], r[f"{col}_{ci_tag}_high"]], [yi, yi], color=c, lw=2,
                    solid_capstyle="round")
            if c == TEXT_SECONDARY:  # reference scenario: open marker
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
    axes[-1].set_xlabel(f"Utility (posterior mean, {credible_interval * 100:g}% credible interval)")
    fig.text(0, -0.01, "Credible intervals reflect posterior uncertainty of the choice-model coefficients only. "
             f"Open marker: {display_name(REFERENCE_SCENARIO)}.", fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout(h_pad=1.8)
    save(fig, name, out_dir)


# ---------------------------------------------------------------------------
# 3. Attribute contribution breakdown (diverging stacked)
# ---------------------------------------------------------------------------
CONTRIBUTION_GROUPS = [  # (label, model terms)
    ("Cost", ["cost"]),
    ("Import", ["import"]),
    ("Land", ["land"]),
    ("Wind share", ["source_wind"]),
    ("Gas share", ["source_gas"]),
    ("Ownership", ["ownership_commercial", "ownership_community"]),
    ("Other (biomass, coal, nuclear, transmission)", ["source_biomass", "source_coal", "source_nuclear", "transmission"]),
]
# Ownership purple instead of dark green (clash with Land), remaining group neutral grey; palette validated
CONTRIBUTION_COLORS = [SERIES[0], SERIES[1], SERIES[2], SERIES[3], SERIES[4], SERIES[6], NEUTRAL]


def compute_contributions(attrs: pd.DataFrame, region: str, scale: dict,
                          model_path: Path = CHOICE_MODEL_PATH, mobile_share: float = 0.0) -> pd.DataFrame:
    """z_k * (beta_real_k + mobile_share * gamma_real_k) per scenario and contribution group, with raw
    attributes z and coefficients in real units (same as utility.compute_utility)."""
    terms = list(ATTRIBUTE_COLUMN_TO_MODEL_TERM.values())
    beta = pd.Series(to_real_units(load_beta_partworths_mean(model_path, country=region).set_index("attribute")["beta_mean"],
                                   scale, terms))
    if mobile_share != 0.0:
        beta = beta + mobile_share * pd.Series(to_real_units(
            load_mobile_partworths_mean(model_path).set_index("attribute")["mobile_mean"], scale, terms))
    rows = {}
    for _, r in attrs.iterrows():
        per_term = raw_attributes(r) * beta.loc[terms]
        rows[r["scenario_id"]] = {label: per_term[terms].sum() for label, terms in CONTRIBUTION_GROUPS}
    return pd.DataFrame(rows).T


def fig_contributions(attrs: pd.DataFrame, rankings: pd.DataFrame, centered: bool, name: str, note: str,
        model_path: Path = CHOICE_MODEL_PATH, out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0,
        attrs_by_region: dict = None) -> None:
    """centered=True: each segment = contribution minus the mean of that attribute over all
    scenarios (per region). Constant terms vanish; what remains visible is what explains the utility
    differences. The diamond then sits at U - mean(U) (= sum of the visible segments); the top axis
    is shifted by mean(U) and shows the true utility there.
    attrs_by_region: attributes per language region (e.g. population-weighted regional attributes, see
    regional_mean_attributes); default: the same attrs for both language regions."""
    scale = load_attribute_scale(model_path)
    order = rankings.sort_values("utility_national", ascending=True)["scenario_id"].tolist()  # best at the top
    regions = [("DE-CH", "DE-CH"), ("FR-CH", "FR-CH")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 6.2), sharey=True)
    for ax, (region, title) in zip(axes, regions):
        region_attrs = attrs if attrs_by_region is None else attrs_by_region[region]
        contrib = compute_contributions(region_attrs, region, scale, model_path, mobile_share)
        offset = contrib.sum(axis=1).mean() if centered else 0.0  # mean(U) over the scenarios
        if centered:
            contrib = contrib - contrib.mean(axis=0)
        contrib = contrib.loc[order]
        y = np.arange(len(order))
        pos = np.zeros(len(order)); neg = np.zeros(len(order))
        for (label, _), color in zip(CONTRIBUTION_GROUPS, CONTRIBUTION_COLORS):
            v = contrib[label].values
            left = np.where(v >= 0, pos, neg)
            ax.barh(y, v, left=left, height=0.7, color=color, edgecolor="white", linewidth=1, label=label)
            pos += np.clip(v, 0, None); neg += np.clip(v, None, 0)
        total = contrib.sum(axis=1).values
        ax.plot(total, y, "D", color=TEXT_PRIMARY, markersize=5.5, markeredgecolor="white",
                markeredgewidth=1, label="Total utility (top axis)" if centered else "Total utility", zorder=4)
        ax.axvline(0, color=TEXT_SECONDARY, lw=1)
        if centered:
            top = ax.secondary_xaxis("top", functions=(lambda x, o=offset: x + o, lambda x, o=offset: x - o))
            top.set_xlabel("Total utility ◆", fontsize=9.5, color=TEXT_SECONDARY)
            top.tick_params(labelsize=9, colors=TEXT_SECONDARY)
            ax.set_title(title, loc="left", fontweight="bold", pad=34)
            ax.set_xlabel("Deviation from scenario mean per attribute\n(β × attribute, real units)")
        else:
            ax.set_title(title, loc="left", fontweight="bold")
            ax.set_xlabel("Contribution to utility (β × attribute, real units)")
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
    fig.text(0, -0.02, note, fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    fig.tight_layout()
    save(fig, name, out_dir)


def mobile_share_note(mobile_share: float) -> str:
    """Footnote addition, only if the mobile effect is mixed in (at 0 the figure stays unchanged)."""
    if mobile_share == 0.0:
        return ""
    return f"\nβ includes the mobile effect: β = beta_partworths + {mobile_share:g} × mobile_partworths."


CONTRIBUTIONS_CENTERED_NOTE = (
    "Segments show the deviation from the scenario mean per attribute, not the absolute contribution "
    "(mean over all 12 scenarios, per region).\nTheir sum is U − mean(U); the diamond marks this sum and is "
    "read as true total utility on the top axis. Scenarios sorted by national utility (highest at top).\n"
    "Absolute contributions incl. constant terms: see Fig. A1."
)
CONTRIBUTIONS_ABSOLUTE_NOTE = (
    "Shows absolute contributions incl. near-constant terms such as ownership; these are not the drivers of "
    "the rank differences – see Fig. 3 for the centered version.\nScenarios sorted by national utility "
    "(highest at top). A negative cost change (price decrease vs. ElCom 2025) contributes positively."
)


# ---------------------------------------------------------------------------
# 4. Slope chart DE-CH vs. FR-CH
# ---------------------------------------------------------------------------
def fig_slope_regions(rankings: pd.DataFrame, out_dir: Path = GRAPHICS_DIR, name: str = "fig4_rank_de_vs_fr") -> None:
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
        scenario = display_name(r["scenario_id"])
        style = dict(fontsize=10, va="center", color=TEXT_PRIMARY if changed else TEXT_SECONDARY,
                     fontweight="bold" if changed else "normal")
        ax.text(-0.05, a, f"{scenario}  {int(a)}", ha="right", **style)
        ax.text(1.05, b, f"{int(b)}  {scenario}", ha="left", **style)
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
    save(fig, name, out_dir)


# ---------------------------------------------------------------------------
# 5. Cost vs. predicted preference (updated version of cost_vs_preference.png)
# ---------------------------------------------------------------------------
def fig_cost_vs_preference(attrs: pd.DataFrame,
        model_path: Path = CHOICE_MODEL_PATH, out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0,
        credible_interval: float = CREDIBLE_INTERVAL, national_samples: dict = None,
        name: str = "fig5_cost_vs_preference") -> None:
    """Top: Mellot cost change vs. EP2050+; bottom: softmax choice share (national) over the
    11 scenarios from Mellot Table 3, with equal-tailed credible interval from the posterior samples.
    national_samples: national utility samples per scenario (e.g. of the regional analysis); default:
    computed from the national attributes with LANGUAGE_REGION_WEIGHTS."""
    q_low, q_high = credible_interval_quantiles(credible_interval)
    df = attrs.dropna(subset=["mellot_cost_change_pct"]).sort_values("mellot_cost_change_pct").reset_index(drop=True)
    if national_samples is None:
        scale = load_attribute_scale(model_path)
        mobile_samples = load_mobile_partworths_samples(model_path) if mobile_share != 0.0 else None
        national = 0
        for region, w in LANGUAGE_REGION_WEIGHTS.items():
            beta_samples = load_beta_partworths_samples(model_path, country=region)
            national = national + w * np.stack([compute_utility_samples(r, beta_samples, scale, mobile_samples=mobile_samples,
                                                                        mobile_share=mobile_share)
                                                for _, r in df.iterrows()])
    else:
        national = np.stack([np.asarray(national_samples[s], dtype=float) for s in df["scenario_id"]])
    shares = compute_choice_shares(dict(zip(df["scenario_id"], national)))
    share = np.array([100 * shares[s].mean() for s in df["scenario_id"]])
    lo = np.array([100 * np.quantile(shares[s], q_low) for s in df["scenario_id"]])
    hi = np.array([100 * np.quantile(shares[s], q_high) for s in df["scenario_id"]])

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
             f"scenarios (IIA assumption),\nbars = posterior mean, whiskers = {credible_interval * 100:g}% credible interval."
             + mobile_share_note(mobile_share),
             fontsize=8.5, color=TEXT_SECONDARY, ha="left")
    fig.tight_layout(h_pad=1.5)
    save(fig, name, out_dir)


# ---------------------------------------------------------------------------
# 6. P(rank 1) vs. ElCom reference price (sensitivity, src/sensitivity.py)
# ---------------------------------------------------------------------------
def _place_label(ax, text: str, candidates: list, obstacles: np.ndarray, placed: list, **style):
    """Put text at the first candidate (x, y, ha, va) whose box overlaps neither obstacle points (data
    coordinates), nor already placed labels, nor leaves the axes; falls back to the first candidate."""
    renderer = ax.figure.canvas.get_renderer()
    points = ax.transData.transform(obstacles) if len(obstacles) else np.empty((0, 2))
    for x, y, ha, va in candidates:
        t = ax.text(x, y, text, ha=ha, va=va, **style)
        extent = t.get_window_extent(renderer)
        box = extent.padded(3)  # fixed margin of 3 px around the text (independent of the text length)
        hit = ((points[:, 0] >= box.x0) & (points[:, 0] <= box.x1)
               & (points[:, 1] >= box.y0) & (points[:, 1] <= box.y1)).any()
        in_axes = ax.bbox.contains(extent.x0, extent.y0) and ax.bbox.contains(extent.x1, extent.y1)
        if not hit and in_axes and not any(box.overlaps(b) for b in placed):
            placed.append(box)
            return t
        t.remove()
    x, y, ha, va = candidates[0]
    xlim = ax.get_xlim()
    ha = "left" if x <= xlim[0] else "right" if x >= xlim[1] else ha  # keep the fallback inside the axes
    t = ax.text(x, y, text, ha=ha, va=va, **style)
    placed.append(t.get_window_extent(renderer))
    return t


# Colour order for the scenarios of fig6 (config sensitivity.figure_scenarios, in that order): blue, orange,
# green, then violet instead of yellow -- yellow (#eda100) and orange (#eb6834) fail the normal-vision
# separation check (dE 13.7 < 15); with violet all pairs pass (CVD dE >= 9.2, normal >= 16.3).
SENSITIVITY_COLORS = [SERIES[0], SERIES[1], SERIES[2], SERIES[6], SERIES[4], SERIES[5]]


def fig_reference_price_sensitivity(curve: pd.DataFrame, crossings: pd.DataFrame, base_years: pd.DataFrame,
                                    switches: pd.DataFrame, scenarios: list, out_dir: Path = GRAPHICS_DIR) -> None:
    """P(rank 1) of the given scenarios vs. the ElCom reference price, one panel per region. Lines: only
    the reference price varies (surcharges and EUR/CHF of the reference year); markers: real base years
    with their own surcharges and annual rate; dashed: changes of the rank-1 scenario (switches).
    crossings only provides the reference-year values for the footnote."""
    colors = dict(zip(scenarios, SENSITIVITY_COLORS))
    panels = [("DE_CH", "DE-CH"), ("FR_CH", "FR-CH"), ("national", "Switzerland (pop.-weighted)")]
    grid = curve[~curve["is_reference_year"]]
    lo, hi = grid["total_rp_kwh"].min(), grid["total_rp_kwh"].max()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), sharey=True)
    for ax, (tag, title) in zip(axes, panels):
        ax.set_title(title, loc="left", fontweight="bold", pad=20)
        ax.set_xlim(lo, hi)
        ax.set_ylim(-0.04, 1.07)
        ax.set_xlabel("ElCom reference price, total (Rp./kWh)")
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("P(rank 1)")
    fig.tight_layout(w_pad=2)  # layout first, so that label boxes are measured at their final position

    for ax, (tag, title) in zip(axes, panels):
        region = grid[grid["region"] == tag]
        obstacles = []
        for s in scenarios:
            c = region[region["scenario_id"] == s].sort_values("total_rp_kwh")
            ax.plot(c["total_rp_kwh"], c["p_rank1"], color=colors[s], lw=2, zorder=3, solid_capstyle="round")
            xs = np.linspace(lo, hi, 400)  # densified curve as obstacle for labels
            obstacles.append(np.column_stack([xs, np.interp(xs, c["total_rp_kwh"], c["p_rank1"])]))
        region_switches = switches[switches["region"] == tag].sort_values("switch_rp_kwh")
        for xc in region_switches["switch_rp_kwh"]:
            ax.axvline(xc, color=NEUTRAL, lw=1, ls="--", zorder=1)
            obstacles.append(np.column_stack([np.full(400, xc), np.linspace(*ax.get_ylim(), 400)]))
        years = base_years[base_years["region"] == tag]
        markers = years[years["scenario_id"].isin(scenarios)]
        for _, r in markers.iterrows():
            ax.plot(r["total_rp_kwh"], r["p_rank1"], "o", color=colors[r["scenario_id"]], markersize=7,
                    markeredgecolor="white", markeredgewidth=1.5, zorder=5)
        obstacles.append(markers[["total_rp_kwh", "p_rank1"]].to_numpy())
        obstacles = np.vstack(obstacles)
        placed = []
        # switch labels ("before -> after", price) next to their line, as high up as there is room
        for _, sw in region_switches.iterrows():
            xc = sw["switch_rp_kwh"]
            text = f"{display_name(sw['scenario_before'])} →\n{display_name(sw['scenario_after'])} ({xc:.1f})"
            cands = [(xc + dx, y, ha, "top") for y in np.arange(1.06, 0.3, -0.04)
                     for dx, ha in [(0.15, "left"), (-0.15, "right")]]
            _place_label(ax, text, cands, obstacles, placed, fontsize=8, color=TEXT_SECONDARY)
        # year labels next to the marker of the first figure scenario
        for _, r in markers[markers["scenario_id"] == scenarios[0]].iterrows():
            x, y = r["total_rp_kwh"], r["p_rank1"]
            ring = [(x + k * dx, y + k * dy, ha, va) for k in (1, 2)  # next to the marker
                    for dx, dy, ha, va in [(0, 0.04, "center", "bottom"), (-0.25, 0.03, "right", "bottom"),
                                           (0.25, 0.03, "left", "bottom"), (0.25, -0.03, "left", "top"),
                                           (-0.25, -0.03, "right", "top"), (0, -0.05, "center", "top")]]
            # wider search around the marker, nearest first; such labels get a leader line
            span_x, span_y = (hi - lo) / 5, 0.3
            far = sorted([(x + fx * span_x, y + fy * span_y, "center", "center")
                          for fx in np.linspace(-1, 1, 13) for fy in np.linspace(-1, 1, 13)],
                         key=lambda c: np.hypot((c[0] - x) / span_x, (c[1] - y) / span_y))
            label = _place_label(ax, str(int(r["year"])), ring + far, obstacles, placed,
                                 fontsize=8.5, color=TEXT_PRIMARY, zorder=6)
            if label.get_position() not in [(cx, cy) for cx, cy, _, _ in ring]:
                ax.annotate("", xy=(x, y), xytext=label.get_position(), zorder=4,
                            arrowprops=dict(arrowstyle="-", lw=0.6, color=TEXT_SECONDARY, shrinkA=6, shrinkB=4))
        if tag == panels[0][0]:  # direct scenario labels in the first panel
            for s in scenarios:
                c = region[region["scenario_id"] == s].sort_values("total_rp_kwh", ascending=False)
                # walk along the curve, starting at the end where it is highest
                if c["p_rank1"].iloc[-1] > c["p_rank1"].iloc[0]:
                    c = c.iloc[::-1]
                cands = [(x, p + dy, ha, "bottom" if dy > 0 else "top")
                         for dy in (0.02, 0.05, -0.03, -0.08, -0.15, -0.25)   # close to the curve first
                         for x, p in zip(c["total_rp_kwh"], c["p_rank1"])
                         for ha in ("center", "left", "right")]
                cands = [(min(max(x, lo), hi), y, ha, va) for x, y, ha, va in cands]
                _place_label(ax, textwrap.fill(display_name(s), 16), cands, obstacles, placed,  # long names on 2 lines
                             fontsize=9, color=TEXT_PRIMARY, fontweight="bold")
    taxes = crossings["taxes_levies_rp_kwh"].iloc[0]
    grid_usage = crossings["netznutzung_rp_kwh"].iloc[0]
    rate = crossings["eur_to_chf"].iloc[0]
    year = int(crossings["reference_year"].iloc[0])
    fig.text(0, -0.06,
             f"Lines: only the reference price varies; taxes/levies ({taxes:.2f} Rp./kWh), grid usage "
             f"({grid_usage:.2f} Rp./kWh) and EUR/CHF ({rate:.4f}, annual mean) as in {year}.\n"
             "Markers: real base years (labelled at the Alpine PV marker) with their own surcharges and annual "
             "EUR/CHF rate, same colours as the lines; therefore not exactly on the lines.\n"
             "Dashed: reference price at which the rank-1 scenario changes (posterior-mean utility), "
             "labelled 'before → after (price)'.",
             fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, "fig6_p_rank1_vs_reference_price", out_dir)


# ---------------------------------------------------------------------------
# Regional main analysis (src/regional.py): figures with the suffix _regional
# ---------------------------------------------------------------------------
def regional_mean_attributes(attributes: pd.DataFrame, weights: pd.Series, language: str) -> pd.DataFrame:
    """Population-weighted mean attributes of the included regions of one language region. The utility is
    linear in the attributes, so contributions computed from these means equal the population-weighted
    mean of the regional contributions (same coefficients within a language region)."""
    members = [r for r in weights.index if CANTON_LANGUAGE.get(r) == language]
    w = weights[members] / weights[members].sum()
    a = attributes[attributes["region"].isin(members)]
    columns = list(ATTRIBUTE_COLUMN_TO_MODEL_TERM)
    mean = a[columns].mul(a["region"].map(w), axis=0).groupby(a["scenario_id"], sort=False).sum()
    first = a.drop_duplicates("scenario_id").set_index("scenario_id")[["mellot_cost_change_pct"]]
    return mean.join(first).reset_index()


def fig_reference_price_shift(curve: pd.DataFrame, switches: pd.DataFrame, scenarios: list,
                              national_reference: float, out_dir: Path = GRAPHICS_DIR,
                              name: str = "fig6_p_rank1_vs_reference_price_shift_regional") -> None:
    """Regional analogue of fig6: P(rank 1) vs. a common shift of all regional reference prices; top axis:
    national median reference price plus the shift (orientation only). Dashed: rank-1 changes."""
    colors = dict(zip(scenarios, SENSITIVITY_COLORS))
    panels = [("DE_CH", "DE-CH"), ("FR_CH", "FR-CH"), ("national", "Switzerland (pop.-weighted)")]
    grid = curve[~curve["is_reference_year"]]
    lo, hi = grid["shift_rp_kwh"].min(), grid["shift_rp_kwh"].max()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), sharey=True)
    for ax, (tag, title) in zip(axes, panels):
        ax.set_title(title, loc="left", fontweight="bold", pad=34)
        ax.set_xlim(lo, hi)
        ax.set_ylim(-0.04, 1.07)
        ax.set_xlabel("Shift of all regional reference prices Δ (Rp./kWh)")
        top = ax.secondary_xaxis("top", functions=(lambda x: x + national_reference, lambda x: x - national_reference))
        top.set_xlabel("National median + Δ (Rp./kWh)", fontsize=9.5, color=TEXT_SECONDARY)
        top.tick_params(labelsize=9, colors=TEXT_SECONDARY)
        ax.axvline(0, color=TEXT_SECONDARY, lw=1, zorder=1)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("P(rank 1)")
    fig.tight_layout(w_pad=2)

    for ax, (tag, title) in zip(axes, panels):
        region = grid[grid["region"] == tag]
        obstacles = []
        for s in scenarios:
            c = region[region["scenario_id"] == s].sort_values("shift_rp_kwh")
            ax.plot(c["shift_rp_kwh"], c["p_rank1"], color=colors[s], lw=2, zorder=3, solid_capstyle="round")
            xs = np.linspace(lo, hi, 400)
            obstacles.append(np.column_stack([xs, np.interp(xs, c["shift_rp_kwh"], c["p_rank1"])]))
        obstacles.append(np.column_stack([np.zeros(400), np.linspace(*ax.get_ylim(), 400)]))
        region_switches = switches[switches["region"] == tag].sort_values("switch_shift_rp_kwh")
        for xc in region_switches["switch_shift_rp_kwh"]:
            ax.axvline(xc, color=NEUTRAL, lw=1, ls="--", zorder=1)
            obstacles.append(np.column_stack([np.full(400, xc), np.linspace(*ax.get_ylim(), 400)]))
        obstacles = np.vstack(obstacles)
        placed = []
        _place_label(ax, "2025 prices", [(0.15, 0.5, "left", "center"), (-0.15, 0.5, "right", "center")]
                     + [(0.15, y, "left", "center") for y in np.arange(0.95, 0.05, -0.05)],
                     obstacles, placed, fontsize=8, color=TEXT_SECONDARY)
        for _, sw in region_switches.iterrows():
            xc = sw["switch_shift_rp_kwh"]
            text = f"{display_name(sw['scenario_before'])} →\n{display_name(sw['scenario_after'])} ({xc:+.1f})"
            cands = [(xc + dx, y, ha, "top") for y in np.arange(1.06, 0.3, -0.04)
                     for dx, ha in [(-0.15, "right"), (0.15, "left")]]
            _place_label(ax, text, cands, obstacles, placed, fontsize=8, color=TEXT_SECONDARY)
        if tag == panels[0][0]:
            for s in scenarios:
                c = region[region["scenario_id"] == s].sort_values("shift_rp_kwh", ascending=False)
                if c["p_rank1"].iloc[-1] > c["p_rank1"].iloc[0]:
                    c = c.iloc[::-1]
                cands = [(x, p + dy, ha, "bottom" if dy > 0 else "top")
                         for dy in (0.02, 0.05, -0.03, -0.08, -0.15, -0.25)
                         for x, p in zip(c["shift_rp_kwh"], c["p_rank1"])
                         for ha in ("center", "left", "right")]
                cands = [(min(max(x, lo), hi), y, ha, va) for x, y, ha, va in cands]
                _place_label(ax, textwrap.fill(display_name(s), 16), cands, obstacles, placed,
                             fontsize=9, color=TEXT_PRIMARY, fontweight="bold")
    fig.text(0, -0.06,
             "All regional ElCom reference prices are shifted by the same Δ; taxes/levies, grid usage and EUR/CHF "
             "stay at their 2025 values. Δ = 0: 2025 prices (solid vertical line).\n"
             f"Top axis: national median reference price 2025 ({national_reference:.3f} Rp./kWh) plus Δ, "
             "for orientation only. Dashed: shift at which the rank-1 scenario changes (posterior-mean utility), "
             "labelled 'before → after (Δ)'.",
             fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir)


# Schematic tile layout of the 23 Calliope regions (column, row; row 0 at the top), roughly geographic
REGION_TILES = {
    "BL_BS": (2, 0), "SH": (4, 0),
    "JU": (1, 1), "SO": (2, 1), "AG": (3, 1), "ZH": (4, 1), "TG": (5, 1),
    "NE": (1, 2), "BE": (2, 2), "LU": (3, 2), "ZG": (4, 2), "SZ": (5, 2), "AI_AR": (6, 2),
    "VD": (1, 3), "FR": (2, 3), "NW_OW": (3, 3), "UR": (4, 3), "GL": (5, 3), "SG": (6, 3),
    "GE": (0, 4), "VS": (2, 4), "TI": (4, 4), "GR": (5, 4),
}
REGION_TILE_LABELS = {"BL_BS": "BL/BS", "AI_AR": "AI/AR", "NW_OW": "NW/OW"}
DARK_TEXT_FILLS = {SERIES[1], SERIES[2]}  # orange and green: dark text, others white (contrast)


def fig_rank1_by_region(regions: pd.DataFrame, scenarios: list, out_dir: Path = GRAPHICS_DIR,
                        name: str = "fig7_rank1_by_region_regional") -> None:
    """Schematic tile map: scenario with rank 1 (posterior-mean utility) per region, with its P(rank 1).
    Colours as in fig6 (sensitivity.figure_scenarios); bold outline = FR-CH; excluded regions hatched."""
    colors = dict(zip(scenarios, SENSITIVITY_COLORS))
    first = regions[regions["rank"] == 1].set_index("region")
    fig, ax = plt.subplots(figsize=(8.0, 5.6))
    size = 0.92
    for region, (col, row) in REGION_TILES.items():
        x, y = col, -row
        label = REGION_TILE_LABELS.get(region, region)
        if region in first.index:
            s = first.loc[region, "scenario_id"]
            fill = colors.get(s, NEUTRAL)
            text = TEXT_PRIMARY if fill in DARK_TEXT_FILLS or fill == NEUTRAL else "white"
            fr = first.loc[region, "language"] == "FR-CH"
            ax.add_patch(plt.Rectangle((x - size / 2, y - size / 2), size, size, facecolor=fill,
                                       edgecolor=TEXT_PRIMARY if fr else "white", linewidth=2.2 if fr else 1))
            ax.text(x, y + 0.12, label, ha="center", va="center", fontsize=10.5, fontweight="bold", color=text)
            ax.text(x, y - 0.2, f"{first.loc[region, 'p_rank1']:.2f}", ha="center", va="center", fontsize=8.5,
                    color=text)
        else:
            ax.add_patch(plt.Rectangle((x - size / 2, y - size / 2), size, size, facecolor="white",
                                       edgecolor=NEUTRAL, hatch="///", linewidth=1))
            ax.text(x, y + 0.12, label, ha="center", va="center", fontsize=10.5, fontweight="bold",
                    color=TEXT_SECONDARY, bbox=dict(facecolor="white", edgecolor="none", pad=1))
            ax.text(x, y - 0.2, "excluded", ha="center", va="center", fontsize=8, color=TEXT_SECONDARY,
                    bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.set_xlim(-0.6, 6.6)
    ax.set_ylim(-4.6, 0.6)
    ax.set_aspect("equal")
    ax.axis("off")
    leaders = [s for s in scenarios if s in set(first["scenario_id"])]
    others = sorted(set(first["scenario_id"]) - set(scenarios))
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=colors.get(s, NEUTRAL), edgecolor="white", label=display_name(s))
               for s in leaders + others]
    handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=TEXT_PRIMARY, linewidth=2.2,
                                 label="FR-CH (bold outline)"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False)
    fig.text(0.02, -0.04, "Scenario with rank 1 per region (posterior-mean utility); number = its P(rank 1) in "
             "that region. Schematic layout, tiles not to scale.\nTI is excluded (no coefficients for the "
             "Italian-speaking region in the choice model).", fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir)


def fig_rank1_population_share(share: pd.DataFrame, rankings: pd.DataFrame, scenarios: list,
                               out_dir: Path = GRAPHICS_DIR,
                               name: str = "fig8_rank1_population_share_regional") -> None:
    """Share of the population (included regions) living in regions where a scenario has rank 1; only
    scenarios with a non-zero share. Colours as in fig6/fig7."""
    colors = dict(zip(scenarios, SENSITIVITY_COLORS))
    df = share[share["population_share_rank1"] > 0].sort_values("population_share_rank1").reset_index(drop=True)
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(6.5, 0.6 * len(df) + 1.4))
    ax.barh(y, 100 * df["population_share_rank1"], height=0.6,
            color=[colors.get(s, NEUTRAL) for s in df["scenario_id"]], edgecolor="white", linewidth=1)
    for yi, v in zip(y, df["population_share_rank1"]):
        ax.text(100 * v + 0.8, yi, f"{100 * v:.1f}%", va="center", ha="left", fontsize=10, color=TEXT_PRIMARY)
    ax.set_yticks(y)
    ax.set_yticklabels([display_name(s) for s in df["scenario_id"]])
    ax.set_xlim(0, 100 * df["population_share_rank1"].max() * 1.2)
    ax.set_xlabel("Population in regions where the scenario has rank 1 (%)")
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    leader = rankings.set_index("scenario_id")["rank_national"].idxmin()
    fig.text(0, -0.08, "Share of the population of the 22 included regions (TI excluded, BFS STATPOP 2024); "
             "all other scenarios 0.\n"
             f"Not the same as the national ranking, where {display_name(leader)} has rank 1.",
             fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir)


CONTRIBUTIONS_REGIONAL_NOTE = (
    "\nRegional analysis: contributions are population-weighted means over the regions of each language region "
    "(TI excluded)."
)


def make_all_regional(attributes: pd.DataFrame, weights: pd.Series, rankings: pd.DataFrame,
                      regions: pd.DataFrame, share: pd.DataFrame, curve: pd.DataFrame, switches: pd.DataFrame,
                      national_samples: dict, national_reference: float, scenarios: list,
                      model_path: Path = CHOICE_MODEL_PATH, out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0,
                      credible_interval: float = CREDIBLE_INTERVAL) -> None:
    """Figures of the regional main analysis (suffix _regional; list in the Snakefile: FIGURES_REGIONAL)."""
    by_language = {l: regional_mean_attributes(attributes, weights, l) for l in ("DE-CH", "FR-CH")}
    first = attributes.drop_duplicates("scenario_id")[["scenario_id", "mellot_cost_change_pct"]]
    fig_rank_vs_cost(rankings, out_dir=out_dir, name="fig1_rank_choice_vs_cost_regional")
    fig_forest(rankings, out_dir=out_dir, credible_interval=credible_interval, name="fig2_utility_forest_regional")
    fig_contributions(first, rankings, centered=True, name="fig3_utility_contributions_regional",
                      note=CONTRIBUTIONS_CENTERED_NOTE + CONTRIBUTIONS_REGIONAL_NOTE + mobile_share_note(mobile_share),
                      model_path=model_path, out_dir=out_dir, mobile_share=mobile_share, attrs_by_region=by_language)
    fig_contributions(first, rankings, centered=False, name="figA1_utility_contributions_absolute_regional",
                      note=CONTRIBUTIONS_ABSOLUTE_NOTE + CONTRIBUTIONS_REGIONAL_NOTE + mobile_share_note(mobile_share),
                      model_path=model_path, out_dir=out_dir, mobile_share=mobile_share, attrs_by_region=by_language)
    fig_slope_regions(rankings, out_dir=out_dir, name="fig4_rank_de_vs_fr_regional")
    fig_cost_vs_preference(first, model_path=model_path, out_dir=out_dir, mobile_share=mobile_share,
                           credible_interval=credible_interval, national_samples=national_samples,
                           name="fig5_cost_vs_preference_regional")
    fig_reference_price_shift(curve, switches, scenarios, national_reference, out_dir=out_dir)
    fig_rank1_by_region(regions, scenarios, out_dir=out_dir)
    fig_rank1_population_share(share, rankings, scenarios, out_dir=out_dir)


def pairwise_order_note(order: list, cost: pd.Series, by_cost: bool) -> str:
    """Footnote on the scenario order of the matrix."""
    if not by_cost:
        return "Scenario order as set in config/default.yaml (pairwise.scenario_order)."
    without = [display_name(s) for s in order if pd.isna(cost.get(s))]
    tail = f"; {', '.join(without)}: no cost value, last" if without else ""
    return f"Scenarios ordered by system cost change (Mellot et al. 2024, Table 3, cheapest first){tail}."


# ---------------------------------------------------------------------------
# Pairwise choice probability matrix (as in Tröndle et al. 2025, Fig. 2/4; src/pairwise.py)
# ---------------------------------------------------------------------------
def fig_pairwise_matrix(matrix: pd.DataFrame, credible_interval: float, out_dir: Path = GRAPHICS_DIR,
                        order_note: str = "", decimals: int = 1, name: str = "fig9_pairwise_choice_probability_regional",
                        formats=("png", "pdf")) -> None:
    """Lower triangle incl. diagonal: P(scenario 1 (row) > scenario 2 (column)) in %, expected value large,
    credible interval small below. Colour: orange (0 %) - beige (50 %) - blue (100 %)."""
    order = matrix.sort_values("row").drop_duplicates("row")["scenario_1"].tolist()
    n = len(order)
    lower = matrix[matrix["column"] <= matrix["row"]]
    grid = np.full((n, n), np.nan)
    grid[lower["row"], lower["column"]] = lower["p_mean"]
    fig, ax = plt.subplots(figsize=(17, 16))
    image = ax.imshow(np.ma.masked_invalid(grid), cmap=CHOICE_CMAP, vmin=0, vmax=1, aspect="equal")
    for _, r in lower.iterrows():
        color = text_color_on(CHOICE_CMAP(r["p_mean"]))
        ax.text(r["column"], r["row"] - 0.1, f"{100 * r['p_mean']:.{decimals}f}%", ha="center", va="center",
                fontsize=11.5, fontweight="bold", color=color)
        ax.text(r["column"], r["row"] + 0.25, f"({100 * r['p_low']:.{decimals}f}–{100 * r['p_high']:.{decimals}f}%)",
                ha="center", va="center", fontsize=7.8, color=color)
    labels = [display_name(s) for s in order]
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", rotation_mode="anchor")
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylabel("Scenario 1", color=SCENARIO_1_COLOR, fontweight="bold", fontsize=13)
    ax.set_xlabel("Scenario 2", color=SCENARIO_2_COLOR, fontweight="bold", fontsize=13)
    bar = fig.colorbar(image, ax=ax, orientation="horizontal", fraction=0.03, pad=0.19, aspect=40, shrink=0.8)
    bar.set_label("Choice probability scenario 1", fontsize=11.5)
    bar.set_ticks([0, 0.25, 0.5, 0.75, 1])
    bar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
    bar.outline.set_visible(False)
    fig.text(0.02, 0.01, "Probability that scenario 1 (row) is chosen over scenario 2 (column) in a pairwise "
             "comparison; posterior mean over the draws,\n"
             f"in brackets the {credible_interval * 100:g}% equal-tailed credible interval. Regional analysis: "
             "population-weighted mean of the regional choice probabilities (TI excluded).\n" + order_note,
             fontsize=8.5, color=TEXT_SECONDARY, ha="left", va="top")
    save(fig, name, out_dir, formats)


def make_all(attrs: pd.DataFrame, rankings: pd.DataFrame, model_path: Path = CHOICE_MODEL_PATH,
             out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0,
             credible_interval: float = CREDIBLE_INTERVAL) -> None:
    """All thesis figures to out_dir (png/pdf/svg each; list in the Snakefile: FIGURES).
    credible_interval must be the value the rankings were computed with (fig2 reads its columns).
    mobile_share must be the same value the rankings were computed with (fig3/A1/fig5 compute
    the utility themselves from the betas)."""
    fig_rank_vs_cost(rankings, out_dir=out_dir)
    fig_forest(rankings, out_dir=out_dir, credible_interval=credible_interval)
    fig_contributions(attrs, rankings, centered=True, name="fig3_utility_contributions",
                      note=CONTRIBUTIONS_CENTERED_NOTE + mobile_share_note(mobile_share), model_path=model_path,
                      out_dir=out_dir, mobile_share=mobile_share)
    fig_contributions(attrs, rankings, centered=False, name="figA1_utility_contributions_absolute",
                      note=CONTRIBUTIONS_ABSOLUTE_NOTE + mobile_share_note(mobile_share), model_path=model_path,
                      out_dir=out_dir, mobile_share=mobile_share)
    fig_slope_regions(rankings, out_dir=out_dir)
    fig_cost_vs_preference(attrs, model_path=model_path, out_dir=out_dir, mobile_share=mobile_share,
                           credible_interval=credible_interval)


if __name__ == "__main__":
    attrs, rankings = load_results()
    make_all(attrs, rankings)
    print(f"Saved graphics to {GRAPHICS_DIR}")
