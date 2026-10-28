"""
Thesis figures (static, Matplotlib). Regional main analysis (make_all_regional, suffix _regional) and national
aggregate for the appendix (make_all, suffix _national). Every figure states its analysis, credible interval and
price year (plot_style.FigureSettings), uses the same scenario order (config figures.scenario_order) and the same
scenario colours (config figures.highlight_scenarios). Saves each figure as PNG (300 dpi), PDF and SVG.
"""

import textwrap
from decimal import ROUND_HALF_UP, Decimal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

from config import (
    PROJECT_ROOT, CHOICE_MODEL_PATH, ATTRIBUTE_COLUMN_TO_MODEL_TERM, SCENARIO_DISPLAY_NAMES,
    LANGUAGE_REGION_WEIGHTS, CANTON_LANGUAGE,
)
from load_data import (
    load_beta_partworths_mean, load_beta_partworths_samples,
    load_mobile_partworths_mean, load_mobile_partworths_samples,
)
from utility import (
    load_attribute_scale, raw_attributes, to_real_units, compute_utility_samples, compute_choice_shares,
)
from intervals import credible_interval as interval_of, credible_interval_tag
from pairwise import scenario_order
from plot_style import (  # colours, Matplotlib settings, save() and FigureSettings shared with the map figures
    TEXT_PRIMARY, TEXT_SECONDARY, NEUTRAL, GRID, CHOICE_CMAP, SCENARIO_1_COLOR, SCENARIO_2_COLOR, ATTRIBUTE_COLORS,
    FigureSettings, save, text_color_on,
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GRAPHICS_DIR = PROJECT_ROOT / "graphics"

REFERENCE_SCENARIO = "baseline"  # not in Mellot Table 3
GROUPS = ["national", "DE_CH", "FR_CH"]  # panel order: Switzerland, DE-CH, FR-CH
LANGUAGES = ["DE-CH", "FR-CH"]


def display_name(scenario_id: str) -> str:
    return SCENARIO_DISPLAY_NAMES.get(scenario_id, scenario_id)


def round_half_up(value: float, decimals: int = 2) -> str:
    """28.965 -> '28.97' (format() rounds the binary value 28.96499... down)."""
    return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def footnote(fig, text: str, fs: FigureSettings, x: float = 0, y: float = -0.02, **kwargs) -> None:
    """Footnote with the analysis, interval and year as last line."""
    fig.text(x, y, (text + "\n" if text else "") + fs.stamp(), fontsize=8.5, color=TEXT_SECONDARY, ha="left",
             va="top", **kwargs)


def scenario_handles(fs: FigureSettings, shown: list, marker: str = "o", others: bool = True) -> list:
    """Legend entries of the highlighted scenarios (in figure order) and one entry for all other scenarios."""
    handles = [plt.Line2D([], [], marker=marker, ls="", color=fs.color(s), markersize=8, label=display_name(s))
               for s in fs.highlight if s in shown]
    if others and any(s not in fs.highlight for s in shown):
        handles.append(plt.Line2D([], [], marker=marker, ls="", color=NEUTRAL, markersize=8, label="Other scenarios"))
    return handles


def load_results(attrs_path: Path = PROCESSED_DIR / "scenario_attributes_summary.csv",
                 rankings_path: Path = PROCESSED_DIR / "utility_rankings.csv") -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(attrs_path), pd.read_csv(rankings_path)


# ---------------------------------------------------------------------------
# 1. Preference rank vs. Mellot cost rank, both on the 11 scenarios with a cost value
# ---------------------------------------------------------------------------
def fig_rank_vs_cost(rankings: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    df = rankings.dropna(subset=["mellot_cost_change_pct"]).copy()
    df["preference_rank"] = df["utility_national"].rank(ascending=False, method="min").astype(int)
    df["cost_rank"] = df["mellot_cost_change_pct"].rank(method="min").astype(int)
    df["diff"] = df["preference_rank"] - df["cost_rank"]
    n = len(df)

    fig, ax = plt.subplots(figsize=(6.5, 6.0))
    ax.plot([0.5, n + 0.5], [0.5, n + 0.5], ls="--", lw=1, color=NEUTRAL, zorder=1)
    ax.scatter(df["cost_rank"], df["preference_rank"], s=80, c=[fs.color(s) for s in df["scenario_id"]],
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
        ax.annotate(label, (r["cost_rank"], r["preference_rank"]), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va="center", fontsize=10 if highlight else 9.5,
                    fontweight="bold" if highlight else "normal",
                    color=TEXT_PRIMARY if highlight else TEXT_SECONDARY)
    ax.set_xlim(0.5, n + 0.5)
    ax.set_ylim(n + 0.5, 0.5)  # rank 1 at the top
    ax.set_xticks(range(1, n + 1))
    ax.set_yticks(range(1, n + 1))
    ax.set_xlabel("Cost rank, Mellot et al. (2024) Table 3 (1 = cheapest)")
    ax.set_ylabel("Predicted preference rank, CH (1 = most preferred)")
    handles = scenario_handles(fs, df["scenario_id"].tolist()) + [
        plt.Line2D([], [], ls="--", lw=1, color=NEUTRAL, label="Identical rank (diagonal)")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.11), ncol=3, frameon=False)
    footnote(fig, f"Both ranks among the {n} scenarios with a cost value; {display_name(REFERENCE_SCENARIO)} has none "
             "and is excluded from both.\nAbove the diagonal: preferred more than the cost rank suggests. "
             "In brackets: preference rank − cost rank for |Δ| ≥ 2.", fs, y=-0.17)
    save(fig, "fig1_rank_choice_vs_cost" + fs.suffix, out_dir)


# ---------------------------------------------------------------------------
# 2. Forest plot: utility with credible interval
# ---------------------------------------------------------------------------
def fig_forest(rankings: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    ci_tag = credible_interval_tag(fs.credible_interval, fs.interval_type)
    df = rankings.set_index("scenario_id").loc[list(fs.order)].reset_index()
    y = np.arange(len(df))[::-1]  # first scenario of the order at the top
    fig, axes = plt.subplots(3, 1, figsize=(6.5, 11), sharex=True)
    for ax, tag in zip(axes, GROUPS):
        col = f"utility_{tag}"
        for yi, (_, r) in zip(y, df.iterrows()):
            c = fs.color(r["scenario_id"])
            ax.plot([r[f"{col}_{ci_tag}_low"], r[f"{col}_{ci_tag}_high"]], [yi, yi], color=c, lw=2,
                    solid_capstyle="round")
            if r["scenario_id"] == REFERENCE_SCENARIO:  # reference scenario: open marker
                ax.plot(r[col], yi, "o", color=c, markersize=7, mfc="white", mec=c, markeredgewidth=1.8)
            else:
                ax.plot(r[col], yi, "o", color=c, markersize=7, markeredgecolor="white", markeredgewidth=1.5)
            ax.text(1.0, yi, f"#{int(r[f'rank_{tag}'])}", transform=ax.get_yaxis_transform(), ha="left",
                    va="center", fontsize=8.5, color=TEXT_SECONDARY)
        ax.set_yticks(y)
        ax.set_yticklabels([display_name(s) for s in df["scenario_id"]])
        for lbl, s in zip(ax.get_yticklabels(), df["scenario_id"]):
            if s == REFERENCE_SCENARIO:
                lbl.set_color(TEXT_SECONDARY); lbl.set_fontstyle("italic")
        ax.set_ylim(-0.6, len(df) - 0.4)
        ax.set_title(fs.title(tag), loc="left", fontweight="bold")
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[-1].set_xlabel(f"Utility (posterior mean, {fs.interval()})")
    fig.tight_layout(h_pad=1.8)
    footnote(fig, "Intervals reflect posterior uncertainty of the choice-model coefficients only; #n = rank in the "
             f"group. Open marker: {display_name(REFERENCE_SCENARIO)}.\n{fs.order_note}", fs, y=0.0)
    save(fig, "fig2_utility_forest" + fs.suffix, out_dir)


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
CONTRIBUTION_LABEL = r"$\tilde\beta$ × attribute value (per unit of the attribute)"


def compute_contributions(attrs: pd.DataFrame, region: str, scale: dict,
                          model_path: Path = CHOICE_MODEL_PATH, mobile_share: float = 0.0) -> pd.DataFrame:
    """z_k * (beta_real_k + mobile_share * gamma_real_k) per scenario and contribution group, with raw
    attributes z and coefficients in real units (same as utility.compute_utility). With the posterior-mean
    coefficients this equals the posterior mean of the per-draw contributions (linear in beta)."""
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


def group_contributions(attrs_by_language: dict, language_weights: dict, model_path: Path = CHOICE_MODEL_PATH,
                        mobile_share: float = 0.0) -> dict:
    """Contributions per group (national, DE_CH, FR_CH). DE-CH/FR-CH: attributes of the language region with its
    coefficients; Switzerland: mean of the two weighted with language_weights (population shares in the regional
    analysis, sample shares in the national aggregate), so that the totals equal utility_<group>."""
    scale = load_attribute_scale(model_path)
    out = {l.replace("-", "_"): compute_contributions(attrs_by_language[l], l, scale, model_path, mobile_share)
           for l in LANGUAGES}
    out["national"] = sum(language_weights[l] * out[l.replace("-", "_")] for l in LANGUAGES)
    return out


def contributions_table(contributions: dict) -> pd.DataFrame:
    """Absolute contributions per group and scenario with their total (= utility of the group)."""
    rows = []
    for group in GROUPS:
        c = contributions[group]
        for s in c.index:
            rows.append({"group": group, "scenario_id": s, **c.loc[s].to_dict(), "total": c.loc[s].sum()})
    return pd.DataFrame(rows)


def fig_contributions(contributions: dict, fs: FigureSettings, centered: bool, name: str, note: str,
                      out_dir: Path = GRAPHICS_DIR) -> None:
    """centered=True: each segment = contribution minus the mean of that attribute over all scenarios (per
    group). Constant terms vanish; what remains visible is what explains the utility differences. The diamond
    then sits at U - mean(U) (= sum of the visible segments); the top axis is shifted by mean(U) and shows the
    true utility there."""
    order = list(fs.order)
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.4), sharey=True)
    for ax, group in zip(axes, GROUPS):
        contrib = contributions[group]
        offset = contrib.sum(axis=1).mean() if centered else 0.0  # mean(U) over the scenarios
        if centered:
            contrib = contrib - contrib.mean(axis=0)
        contrib = contrib.loc[order]
        y = np.arange(len(order))[::-1]  # first scenario of the order at the top
        pos = np.zeros(len(order)); neg = np.zeros(len(order))
        for (label, _), color in zip(CONTRIBUTION_GROUPS, ATTRIBUTE_COLORS):
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
            ax.set_title(fs.title(group), loc="left", fontweight="bold", pad=34, fontsize=11)
            ax.set_xlabel("Deviation from the scenario mean\n" + CONTRIBUTION_LABEL)
        else:
            ax.set_title(fs.title(group), loc="left", fontweight="bold", fontsize=11)
            ax.set_xlabel("Contribution to utility\n" + CONTRIBUTION_LABEL)
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(np.arange(len(order))[::-1])
    axes[0].set_yticklabels([display_name(s) for s in order])
    lo = min(a.get_xlim()[0] for a in axes); hi = max(a.get_xlim()[1] for a in axes)
    for a in axes:
        a.set_xlim(lo, hi)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.55, 1.1),
               title=r"Contribution $\tilde\beta_k \cdot z_k$ of the attribute", title_fontsize=10)
    fig.tight_layout()
    footnote(fig, note + "\n" + fs.order_note, fs)
    save(fig, name + fs.suffix, out_dir)


def mobile_share_note(mobile_share: float) -> str:
    """Footnote addition, only if the mobile effect is mixed in (at 0 the figure stays unchanged)."""
    if mobile_share == 0.0:
        return ""
    return f"\nβ includes the mobile effect: β = beta_partworths + {mobile_share:g} × mobile_partworths."


CONTRIBUTIONS_CENTERED_NOTE = (
    "Segments show the deviation from the scenario mean per attribute (mean over all 12 scenarios, per group), not "
    "the absolute contribution. Their sum is U − mean(U);\nthe diamond marks this sum and is read as true total utility "
    "on the top axis. Bars: posterior-mean coefficients (= posterior mean of the per-draw contributions). "
    "Absolute contributions: Fig. A1."
)
CONTRIBUTIONS_ABSOLUTE_NOTE = (
    "Absolute contributions incl. near-constant terms such as ownership; these do not drive the rank differences "
    "(see Fig. 3).\nA negative cost change (price decrease) contributes positively. Bars: posterior-mean coefficients."
)
CONTRIBUTIONS_REGIONAL_NOTE = (
    "\nDE-CH / FR-CH: population-weighted mean over the regions of the language region; Switzerland: "
    "population-weighted mean of DE-CH and FR-CH."
)
CONTRIBUTIONS_NATIONAL_NOTE = (
    "\nNational attribute values; Switzerland: DE-CH and FR-CH weighted with the survey sample shares 61:23."
)


# ---------------------------------------------------------------------------
# 4. Slope chart DE-CH vs. FR-CH
# ---------------------------------------------------------------------------
def fig_slope_regions(rankings: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    df = rankings.copy()
    fig, ax = plt.subplots(figsize=(6.5, 6.2))
    for _, r in df.iterrows():
        a, b = r["rank_DE_CH"], r["rank_FR_CH"]
        changed = a != b
        color = fs.color(r["scenario_id"])
        lw, z = (2.2, 3) if r["scenario_id"] in fs.highlight else (1.2, 2)
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
    handles = [plt.Line2D([], [], color=h.get_color(), lw=2.2, label=h.get_label())
               for h in scenario_handles(fs, df["scenario_id"].tolist())]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False)
    footnote(fig, "Bold labels: rank differs between DE-CH and FR-CH.", fs, y=0.0)
    save(fig, "fig4_rank_de_vs_fr" + fs.suffix, out_dir)


# ---------------------------------------------------------------------------
# 5. Cost vs. predicted preference
# ---------------------------------------------------------------------------
def fig_cost_vs_preference(attrs: pd.DataFrame, fs: FigureSettings, model_path: Path = CHOICE_MODEL_PATH,
                           out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0,
                           national_samples: dict = None) -> None:
    """Top: Mellot cost change vs. EP2050+; bottom: softmax choice share (national) over the 11 scenarios from
    Mellot Table 3, with credible interval from the posterior samples. national_samples: national utility
    samples per scenario (regional analysis); default: from the national attributes with LANGUAGE_REGION_WEIGHTS."""
    with_cost = attrs.dropna(subset=["mellot_cost_change_pct"]).set_index("scenario_id")
    df = with_cost.loc[[s for s in fs.order if s in with_cost.index]].reset_index()
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
    bounds = [interval_of(shares[s], fs.credible_interval, fs.interval_type) for s in df["scenario_id"]]
    lo = np.array([100 * b[0] for b in bounds])
    hi = np.array([100 * b[1] for b in bounds])

    x = np.arange(len(df))
    fig, (ax_cost, ax_pref) = plt.subplots(2, 1, figsize=(6.5, 6.8), sharex=True, height_ratios=[1, 1.15])
    ax_cost.bar(x, df["mellot_cost_change_pct"], width=0.7, color=NEUTRAL, edgecolor="white", linewidth=1)
    ax_cost.axhline(0, color=TEXT_SECONDARY, lw=1)
    ax_cost.set_ylabel("System cost change\nvs. EP2050+ (%)")
    ax_cost.set_title("Cost (Mellot et al. 2024, Table 3)", loc="left", fontweight="bold")

    ax_pref.bar(x, share, width=0.7, color=[fs.color(s) for s in df["scenario_id"]], edgecolor="white", linewidth=1)
    ax_pref.errorbar(x, share, yerr=[share - lo, hi - share], fmt="none", ecolor=TEXT_PRIMARY, elinewidth=1.2, capsize=3)
    uniform = 100 / len(df)
    ax_pref.axhline(uniform, ls="--", lw=1, color=TEXT_SECONDARY)
    ax_pref.text(len(df) - 0.45, uniform, f"equal share ({uniform:.1f}%)", ha="right", va="bottom",
                 fontsize=9, color=TEXT_SECONDARY)
    ax_pref.set_ylabel("Predicted choice share,\nSwitzerland (%)")
    ax_pref.set_title("Predicted citizen preference (choice model)", loc="left", fontweight="bold")
    ax_pref.set_ylim(0, max(hi) * 1.15)
    ax_pref.set_xticks(x)
    ax_pref.set_xticklabels([display_name(s) for s in df["scenario_id"]], rotation=45, ha="right", rotation_mode="anchor")
    for ax in (ax_cost, ax_pref):
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
    fig.tight_layout(h_pad=1.5)
    footnote(fig, f"Choice shares: multinomial logit over the {len(df)} scenarios with a cost value (IIA assumption); "
             f"bars = posterior mean, whiskers = {fs.interval()}.\n{fs.order_note}" + mobile_share_note(mobile_share),
             fs, y=0.0)
    save(fig, "fig5_cost_vs_preference" + fs.suffix, out_dir)


# ---------------------------------------------------------------------------
# 6. P(rank 1) vs. reference price (sensitivity)
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


def _scenario_curve_labels(ax, region: pd.DataFrame, x_col: str, fs: FigureSettings, lo: float, hi: float,
                           obstacles: np.ndarray, placed: list) -> None:
    """Direct labels of the highlighted scenarios along their curves (first panel only)."""
    for s in fs.highlight:
        c = region[region["scenario_id"] == s].sort_values(x_col, ascending=False)
        if c["p_rank1"].iloc[-1] > c["p_rank1"].iloc[0]:  # walk along the curve, starting where it is highest
            c = c.iloc[::-1]
        cands = [(x, p + dy, ha, "bottom" if dy > 0 else "top")
                 for dy in (0.02, 0.05, -0.03, -0.08, -0.15, -0.25)  # close to the curve first
                 for x, p in zip(c[x_col], c["p_rank1"])
                 for ha in ("center", "left", "right")]
        cands = [(min(max(x, lo), hi), y, ha, va) for x, y, ha, va in cands]
        _place_label(ax, textwrap.fill(display_name(s), 16), cands, obstacles, placed,  # long names on 2 lines
                     fontsize=9, color=TEXT_PRIMARY, fontweight="bold")


def fig_reference_price_sensitivity(curve: pd.DataFrame, crossings: pd.DataFrame, base_years: pd.DataFrame,
                                    switches: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    """National aggregate: P(rank 1) of the highlighted scenarios vs. the ElCom reference price, one panel per
    group. Lines: only the reference price varies (surcharges and EUR/CHF of the reference year); markers: real
    base years with their own surcharges and annual rate; dashed: changes of the rank-1 scenario (switches).
    crossings only provides the reference-year values for the footnote."""
    scenarios = list(fs.highlight)
    grid = curve[~curve["is_reference_year"]]
    lo, hi = grid["total_rp_kwh"].min(), grid["total_rp_kwh"].max()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), sharey=True)
    for ax, tag in zip(axes, GROUPS):
        ax.set_title(fs.title(tag), loc="left", fontweight="bold", pad=20, fontsize=11)
        ax.set_xlim(lo, hi)
        ax.set_ylim(-0.04, 1.07)
        ax.set_xlabel("ElCom reference price, total (Rp./kWh)")
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("P(rank 1)")
    fig.tight_layout(w_pad=2)  # layout first, so that label boxes are measured at their final position

    for ax, tag in zip(axes, GROUPS):
        region = grid[grid["region"] == tag]
        obstacles = []
        for s in scenarios:
            c = region[region["scenario_id"] == s].sort_values("total_rp_kwh")
            ax.plot(c["total_rp_kwh"], c["p_rank1"], color=fs.color(s), lw=2, zorder=3, solid_capstyle="round")
            xs = np.linspace(lo, hi, 400)  # densified curve as obstacle for labels
            obstacles.append(np.column_stack([xs, np.interp(xs, c["total_rp_kwh"], c["p_rank1"])]))
        region_switches = switches[switches["region"] == tag].sort_values("switch_rp_kwh")
        for xc in region_switches["switch_rp_kwh"]:
            ax.axvline(xc, color=NEUTRAL, lw=1, ls="--", zorder=1)
            obstacles.append(np.column_stack([np.full(400, xc), np.linspace(*ax.get_ylim(), 400)]))
        years = base_years[base_years["region"] == tag]
        markers = years[years["scenario_id"].isin(scenarios)]
        for _, r in markers.iterrows():
            ax.plot(r["total_rp_kwh"], r["p_rank1"], "o", color=fs.color(r["scenario_id"]), markersize=7,
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
        # year labels next to the marker of the first highlighted scenario
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
        if tag == GROUPS[0]:
            _scenario_curve_labels(ax, region, "total_rp_kwh", fs, lo, hi, obstacles, placed)
    taxes = crossings["taxes_levies_rp_kwh"].iloc[0]
    grid_usage = crossings["netznutzung_rp_kwh"].iloc[0]
    rate = crossings["eur_to_chf"].iloc[0]
    year = int(crossings["reference_year"].iloc[0])
    footnote(fig, f"Lines: only the national reference price varies; taxes/levies ({taxes:.2f} Rp./kWh), grid usage "
             f"({grid_usage:.2f} Rp./kWh) and EUR/CHF ({rate:.4f}, annual mean) as in {year}.\n"
             f"Markers: real base years (labelled at the {display_name(scenarios[0])} marker) with their own surcharges "
             "and annual EUR/CHF rate, same colours as the lines; therefore not exactly on the lines.\n"
             "Dashed: reference price at which the rank-1 scenario changes (posterior-mean utility), "
             "labelled 'before → after (price)'.", fs, y=-0.06)
    save(fig, "fig6_p_rank1_vs_reference_price" + fs.suffix, out_dir)


# ---------------------------------------------------------------------------
# Regional main analysis (src/regional.py)
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


def language_population_weights(weights: pd.Series) -> dict:
    """Population share of DE-CH and FR-CH among the included regions."""
    return {l: float(weights[[r for r in weights.index if CANTON_LANGUAGE.get(r) == l]].sum()) for l in LANGUAGES}


def fig_reference_price_shift(curve: pd.DataFrame, switches: pd.DataFrame, national_reference: float,
                              fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    """Regional main analysis: P(rank 1) vs. a common additive shift Δ of all regional reference prices; top
    axis: national median reference price plus Δ (orientation only). Dashed: rank-1 changes; solid: Δ = 0."""
    scenarios = list(fs.highlight)
    reference = float(round_half_up(national_reference))
    grid = curve[~curve["is_reference_year"]]
    lo, hi = grid["shift_rp_kwh"].min(), grid["shift_rp_kwh"].max()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), sharey=True)
    for ax, tag in zip(axes, GROUPS):
        ax.set_title(fs.title(tag), loc="left", fontweight="bold", pad=34, fontsize=11)
        ax.set_xlim(lo, hi)
        ax.set_ylim(-0.04, 1.07)
        ax.set_xlabel("Shift of all regional reference prices Δ (Rp./kWh)")
        top = ax.secondary_xaxis("top", functions=(lambda x: x + reference, lambda x: x - reference))
        top.set_xlabel(f"Corresponds to national median {reference:.2f} + Δ (Rp./kWh)", fontsize=9.5,
                       color=TEXT_SECONDARY)
        top.tick_params(labelsize=9, colors=TEXT_SECONDARY)
        ax.axvline(0, color=TEXT_SECONDARY, lw=1, zorder=1)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_ylabel("P(rank 1)")
    fig.tight_layout(w_pad=2)

    for ax, tag in zip(axes, GROUPS):
        region = grid[grid["region"] == tag]
        obstacles = []
        for s in scenarios:
            c = region[region["scenario_id"] == s].sort_values("shift_rp_kwh")
            ax.plot(c["shift_rp_kwh"], c["p_rank1"], color=fs.color(s), lw=2, zorder=3, solid_capstyle="round")
            xs = np.linspace(lo, hi, 400)
            obstacles.append(np.column_stack([xs, np.interp(xs, c["shift_rp_kwh"], c["p_rank1"])]))
        obstacles.append(np.column_stack([np.zeros(400), np.linspace(*ax.get_ylim(), 400)]))
        region_switches = switches[switches["region"] == tag].sort_values("switch_shift_rp_kwh")
        for xc in region_switches["switch_shift_rp_kwh"]:
            ax.axvline(xc, color=NEUTRAL, lw=1, ls="--", zorder=1)
            obstacles.append(np.column_stack([np.full(400, xc), np.linspace(*ax.get_ylim(), 400)]))
        obstacles = np.vstack(obstacles)
        placed = []
        _place_label(ax, f"{fs.year} prices", [(0.15, 0.5, "left", "center"), (-0.15, 0.5, "right", "center")]
                     + [(0.15, y, "left", "center") for y in np.arange(0.95, 0.05, -0.05)],
                     obstacles, placed, fontsize=8, color=TEXT_SECONDARY)
        for _, sw in region_switches.iterrows():
            xc = sw["switch_shift_rp_kwh"]
            text = (f"{display_name(sw['scenario_before'])} →\n{display_name(sw['scenario_after'])} "
                    f"(Δ {xc:+.1f}, ≙ {reference + xc:.1f})")
            cands = [(xc + dx, y, ha, "top") for y in np.arange(1.06, 0.3, -0.04)
                     for dx, ha in [(-0.15, "right"), (0.15, "left")]]
            _place_label(ax, text, cands, obstacles, placed, fontsize=8, color=TEXT_SECONDARY)
        if tag == GROUPS[0]:
            _scenario_curve_labels(ax, region, "shift_rp_kwh", fs, lo, hi, obstacles, placed)
    footnote(fig, "All regional ElCom reference prices are shifted by the same Δ; taxes/levies, grid usage and EUR/CHF "
             f"stay at their {fs.year} values. Solid vertical line: Δ = 0 ({fs.year} prices).\n"
             f"Top axis: national median reference price {fs.year} ({reference:.2f} Rp./kWh) plus Δ, for orientation "
             "only. Dashed: shift at which the rank-1 scenario changes (posterior-mean utility), "
             "labelled 'before → after (Δ, ≙ national median + Δ)'.", fs, y=-0.06)
    save(fig, "fig6_p_rank1_vs_reference_price_shift" + fs.suffix, out_dir)


# Schematic tile layout of the 23 Calliope regions (column, row; row 0 at the top), roughly geographic
REGION_TILES = {
    "BL_BS": (2, 0), "SH": (4, 0),
    "JU": (1, 1), "SO": (2, 1), "AG": (3, 1), "ZH": (4, 1), "TG": (5, 1),
    "NE": (1, 2), "BE": (2, 2), "LU": (3, 2), "ZG": (4, 2), "SZ": (5, 2), "AI_AR": (6, 2),
    "VD": (1, 3), "FR": (2, 3), "NW_OW": (3, 3), "UR": (4, 3), "GL": (5, 3), "SG": (6, 3),
    "GE": (0, 4), "VS": (2, 4), "TI": (4, 4), "GR": (5, 4),
}
REGION_TILE_LABELS = {"BL_BS": "BL/BS", "AI_AR": "AI/AR", "NW_OW": "NW/OW"}


def fig_rank1_by_region(regions: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR) -> None:
    """Schematic tile map: scenario with rank 1 (posterior-mean utility) per region, with its P(rank 1).
    Scenario colours as in all figures; bold outline = FR-CH; excluded regions hatched."""
    first = regions[regions["rank"] == 1].set_index("region")
    fig, ax = plt.subplots(figsize=(8.0, 5.6))
    size = 0.92
    for region, (col, row) in REGION_TILES.items():
        x, y = col, -row
        label = REGION_TILE_LABELS.get(region, region)
        if region in first.index:
            fill = fs.color(first.loc[region, "scenario_id"])
            text = text_color_on(matplotlib.colors.to_rgba(fill))
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
    leaders = [s for s in fs.order if s in set(first["scenario_id"])]
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=fs.color(s), edgecolor="white", label=display_name(s))
               for s in leaders]
    handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="white", edgecolor=TEXT_PRIMARY, linewidth=2.2,
                                 label="FR-CH (bold outline)"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False)
    footnote(fig, "Scenario with rank 1 per region (posterior-mean utility); number = its P(rank 1) in that region. "
             "Schematic layout, tiles not to scale.\nTI is excluded (no coefficients for the Italian-speaking region "
             "in the choice model).", fs, x=0.02, y=-0.04)
    save(fig, "fig7_rank1_by_region" + fs.suffix, out_dir)


def fig_rank1_population_share(share: pd.DataFrame, rankings: pd.DataFrame, fs: FigureSettings,
                               out_dir: Path = GRAPHICS_DIR) -> None:
    """Share of the population (included regions) living in regions where a scenario has rank 1; only
    scenarios with a non-zero share, in the figure order."""
    s = share.set_index("scenario_id")["population_share_rank1"]
    df = pd.DataFrame({"scenario_id": [x for x in fs.order if s.get(x, 0) > 0]})
    df["share"] = df["scenario_id"].map(s)
    y = np.arange(len(df))[::-1]  # first scenario of the order at the top
    fig, ax = plt.subplots(figsize=(6.5, 0.6 * len(df) + 1.4))
    ax.barh(y, 100 * df["share"], height=0.6, color=[fs.color(x) for x in df["scenario_id"]], edgecolor="white",
            linewidth=1)
    for yi, v in zip(y, df["share"]):
        ax.text(100 * v + 0.8, yi, f"{100 * v:.1f}%", va="center", ha="left", fontsize=10, color=TEXT_PRIMARY)
    ax.set_yticks(y)
    ax.set_yticklabels([display_name(x) for x in df["scenario_id"]])
    ax.set_xlim(0, 100 * df["share"].max() * 1.2)
    ax.set_xlabel("Population in regions where the scenario has rank 1 (%)")
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    leader = rankings.set_index("scenario_id")["rank_national"].idxmin()
    footnote(fig, "Share of the population of the 22 included regions (BFS STATPOP 2024); all other scenarios 0. "
             f"Not the national ranking,\nwhere {display_name(leader)} has rank 1. {fs.order_note}", fs, y=-0.08)
    save(fig, "fig8_rank1_population_share" + fs.suffix, out_dir)


def make_all_regional(attributes: pd.DataFrame, weights: pd.Series, rankings: pd.DataFrame,
                      regions: pd.DataFrame, share: pd.DataFrame, curve: pd.DataFrame, switches: pd.DataFrame,
                      national_samples: dict, national_reference: float, fs: FigureSettings,
                      model_path: Path = CHOICE_MODEL_PATH, out_dir: Path = GRAPHICS_DIR,
                      mobile_share: float = 0.0) -> pd.DataFrame:
    """Figures of the regional main analysis (suffix _regional; list in the Snakefile: FIGURES_REGIONAL).
    Returns the absolute contributions per group and scenario (fig3/figA1) with their totals."""
    by_language = {l: regional_mean_attributes(attributes, weights, l) for l in LANGUAGES}
    contributions = group_contributions(by_language, language_population_weights(weights), model_path, mobile_share)
    first = attributes.drop_duplicates("scenario_id")[["scenario_id", "mellot_cost_change_pct"]]
    fig_rank_vs_cost(rankings, fs, out_dir)
    fig_forest(rankings, fs, out_dir)
    fig_contributions(contributions, fs, True, "fig3_utility_contributions",
                      CONTRIBUTIONS_CENTERED_NOTE + CONTRIBUTIONS_REGIONAL_NOTE + mobile_share_note(mobile_share), out_dir)
    fig_contributions(contributions, fs, False, "figA1_utility_contributions_absolute",
                      CONTRIBUTIONS_ABSOLUTE_NOTE + CONTRIBUTIONS_REGIONAL_NOTE + mobile_share_note(mobile_share), out_dir)
    fig_slope_regions(rankings, fs, out_dir)
    fig_cost_vs_preference(first, fs, model_path, out_dir, mobile_share, national_samples)
    fig_reference_price_shift(curve, switches, national_reference, fs, out_dir)
    fig_rank1_by_region(regions, fs, out_dir)
    fig_rank1_population_share(share, rankings, fs, out_dir)
    return contributions_table(contributions)


def make_all(attrs: pd.DataFrame, rankings: pd.DataFrame, fs: FigureSettings, model_path: Path = CHOICE_MODEL_PATH,
             out_dir: Path = GRAPHICS_DIR, mobile_share: float = 0.0) -> pd.DataFrame:
    """Figures of the national aggregate (appendix, suffix _national; list in the Snakefile: FIGURES).
    fs must carry the interval and mobile_share the value the rankings were computed with.
    Returns the absolute contributions per group and scenario (fig3/figA1) with their totals."""
    contributions = group_contributions({l: attrs for l in LANGUAGES}, LANGUAGE_REGION_WEIGHTS, model_path, mobile_share)
    fig_rank_vs_cost(rankings, fs, out_dir)
    fig_forest(rankings, fs, out_dir)
    fig_contributions(contributions, fs, True, "fig3_utility_contributions",
                      CONTRIBUTIONS_CENTERED_NOTE + CONTRIBUTIONS_NATIONAL_NOTE + mobile_share_note(mobile_share), out_dir)
    fig_contributions(contributions, fs, False, "figA1_utility_contributions_absolute",
                      CONTRIBUTIONS_ABSOLUTE_NOTE + CONTRIBUTIONS_NATIONAL_NOTE + mobile_share_note(mobile_share), out_dir)
    fig_slope_regions(rankings, fs, out_dir)
    fig_cost_vs_preference(attrs, fs, model_path, out_dir, mobile_share)
    return contributions_table(contributions)


# ---------------------------------------------------------------------------
# Pairwise choice probability matrix (as in Tröndle et al. 2025, Fig. 2/4; src/pairwise.py)
# ---------------------------------------------------------------------------
def figure_settings(analysis: str, params, cost: pd.Series = None) -> FigureSettings:
    """FigureSettings from the Snakemake params of a plot rule (credible_interval, interval_type, year, order,
    highlight); cost (Mellot cost change per scenario id, all scenarios) gives the figure order."""
    order, note = (), ""
    if cost is not None:
        order = tuple(scenario_order(cost, params.order))
        note = scenario_order_note(list(order), cost, not params.order)
    return FigureSettings(analysis, params.credible_interval, params.interval_type, params.year, order, note,
                          tuple(params.highlight))


def scenario_order_note(order: list, cost: pd.Series, by_cost: bool) -> str:
    """Footnote on the scenario order shared by all figures."""
    if not by_cost:
        return "Scenario order as set in config/default.yaml (figures.scenario_order)."
    without = [display_name(s) for s in order if pd.isna(cost.get(s))]
    tail = f"; {', '.join(without)}: no cost value, last" if without else ""
    return f"Scenarios ordered by system cost change (Mellot et al. 2024, Table 3, cheapest first){tail}."


def fig_pairwise_matrix(matrix: pd.DataFrame, fs: FigureSettings, out_dir: Path = GRAPHICS_DIR, decimals: int = 1,
                        name: str = "fig9_pairwise_choice_probability", formats=("png", "pdf")) -> None:
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
    footnote(fig, "Probability that scenario 1 (row) is chosen over scenario 2 (column) in a pairwise comparison; "
             f"posterior mean over the draws,\nin brackets the {fs.interval()}. Population-weighted mean of the "
             "regional choice probabilities. Orange/blue: scale of the choice probability, not scenario colours.\n"
             + fs.order_note, fs, x=0.02, y=0.01)
    save(fig, name + fs.suffix, out_dir, formats)
