"""
Utility-Berechnung für die Mellot-Szenarien mit dem Jan-2026-Choice-Modell (CHOICE_MODEL_PATH).

Das Modell ist auf skalierten Attributwerten gefittet (constant_data/attribute_values_*_scaled =
Rohwert / Survey-Maximum, z.B. import/0.9, land/0.08, transmission/2.0). Die Szenario-Attribute
(Rohwerte, wie in scenario_attributes_summary) werden deshalb vor der Multiplikation mit Beta
durch dieselben Faktoren geteilt -- verifiziert gegen u_right im Posterior (Abweichung ~1e-15):
    u = sum_k x_scaled[k] * beta_partworths[country, k]
beta_partworths ist der Referenzfall m=0 (Nicht-Mobile-Respondent); mobile_partworths und
left_intercept (Positionseffekt links/rechts) werden bewusst nicht verwendet.
"""

import arviz as az
import numpy as np
import pandas as pd

from config import ATTRIBUTE_COLUMN_TO_MODEL_TERM, LANGUAGE_REGION_WEIGHTS


def load_attribute_scale(data_path) -> dict:
    """Skalierungsfaktor pro Modell-Attribut (Rohwert / skalierter Wert), direkt aus den
    Survey-Daten im Modell-File gelesen statt hart codiert."""
    constant = az.from_netcdf(data_path).constant_data
    raw = constant["attribute_values_left"].max(dim="choice_situation")
    scaled = constant["attribute_values_left_scaled"].max(dim="choice_situation")
    return (raw / scaled).to_series().to_dict()


def scale_scenario_attributes(scenario_row: pd.Series, scale: dict,
                              mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM) -> pd.Series:
    """Szenario-Rohwerte -> skalierte Werte, indexiert nach Modell-Attributname."""
    return pd.Series({term: scenario_row[col] / scale[term] for col, term in mapping.items()})


def compute_utility(scenario_row: pd.Series, beta: pd.DataFrame, scale: dict,
                    mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM) -> float:
    """Punktschätzung: sum(beta_mean * x_scaled) über alle 11 Attribute.
    beta wie von load_beta_partworths_mean() (Spalten attribute, beta_mean)."""
    x = scale_scenario_attributes(scenario_row, scale, mapping)
    beta_mean = beta.set_index("attribute")["beta_mean"]
    return float((x * beta_mean.loc[x.index]).sum())


def compute_utility_samples(scenario_row: pd.Series, beta_samples: dict, scale: dict,
                            mapping: dict = ATTRIBUTE_COLUMN_TO_MODEL_TERM) -> np.ndarray:
    """Utility pro Posterior-Sample (Array der Länge chains*draws), gleiche Sample-Reihenfolge
    wie beta_samples (von load_beta_partworths_samples())."""
    x = scale_scenario_attributes(scenario_row, scale, mapping)
    return sum(x[term] * beta_samples[term] for term in x.index)


def compute_regional_utilities(scenarios: pd.DataFrame, betas_mean: dict, betas_samples: dict,
                               scale: dict, weights: dict = LANGUAGE_REGION_WEIGHTS) -> tuple:
    """Utility pro Szenario und Sprachregion (Keys von weights) plus bevölkerungsgewichtetes
    nationales Mittel.

    Returns
    -------
    (utilities, samples)
        utilities: DataFrame mit scenario_id, utility_<region> und utility_national (Mean-Betas).
        samples: dict region/"national" -> DataFrame (Sample x Szenario).
    """
    utilities = pd.DataFrame({"scenario_id": scenarios["scenario_id"]})
    samples = {}
    for region in weights:
        col = f"utility_{region.replace('-', '_')}"
        utilities[col] = [compute_utility(row, betas_mean[region], scale) for _, row in scenarios.iterrows()]
        samples[region] = pd.DataFrame({row["scenario_id"]: compute_utility_samples(row, betas_samples[region], scale)
                                        for _, row in scenarios.iterrows()})
    utilities["utility_national"] = sum(
        w * utilities[f"utility_{region.replace('-', '_')}"] for region, w in weights.items()
    )
    samples["national"] = sum(w * samples[region] for region, w in weights.items())
    return utilities, samples


def rank_scenarios(utilities: pd.DataFrame, column: str) -> pd.DataFrame:
    """Absteigend nach Utility sortiertes Ranking (Rang 1 = höchste vorhergesagte Präferenz)."""
    ranked = utilities[["scenario_id", column]].sort_values(column, ascending=False).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    return ranked


def compute_pairwise_choice_probability(utility_a, utility_b):
    """P(Szenario A wird gegenueber B bevorzugt), Standard-Logit-Link -- identisch mit dem Link im
    Choice-Modell (p_left = sigmoid(u_left - u_right), verifiziert gegen den Posterior).
    Funktioniert für Floats (Mean-Utility) und elementweise für Sample-Arrays."""
    return 1 / (1 + np.exp(-(np.asarray(utility_a) - np.asarray(utility_b))))


def compute_choice_shares(utilities: dict) -> dict:
    """Anteil, wenn alle Szenarien gleichzeitig zur Wahl stuenden (Softmax, IIA-Annahme --
    methodisch staerkere Annahme als beim paarweisen Vergleich, da nicht dem urspruenglichen
    Survey-Design mit Zweier-Vergleichen entspricht).
    Werte dürfen Floats oder gleich lange Sample-Arrays sein (Softmax dann pro Sample)."""
    names = list(utilities)
    u = np.stack([np.asarray(utilities[k], dtype=float) for k in names])
    exp_u = np.exp(u - u.max(axis=0))  # numerisch stabil, Ergebnis unverändert
    shares = exp_u / exp_u.sum(axis=0)
    return {k: shares[i] if shares.ndim > 1 else float(shares[i]) for i, k in enumerate(names)}
