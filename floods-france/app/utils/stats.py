"""
utils/stats.py — Fonctions statistiques pour l'analyse fréquentielle des crues.

Distributions extrêmes : GEV (L-moments), Gumbel MLE, Log-Normale MLE.
Intervalles de confiance par bootstrap (Efron & Tibshirani).
Données synthétiques comme fallback lorsque les séries historiques sont indisponibles.

Convention ξ : standard (ξ > 0 = Fréchet, queue lourde).
  ↳ scipy.stats.genextreme utilise c = −ξ (signe inversé) — conversion gérée en interne.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import gamma as _gamma


# ── Données synthétiques ───────────────────────────────────────────────────────

def synth_annual_max(
    n: int = 60,
    xi: float = 0.20,
    loc: float = 150.0,
    scale: float = 80.0,
    seed: int = 42,
) -> np.ndarray:
    """
    Génère des maxima annuels synthétiques suivant une loi GEV.

    Parameters
    ----------
    xi : float
        Paramètre de forme en convention **standard** (ξ).
        ξ > 0 → Fréchet (queue lourde) — typique crues cévenoles méditerranéennes.
        ξ < 0 → Weibull (queue bornée).
        ξ = 0 → Gumbel.

    Notes
    -----
    scipy.stats.genextreme utilise c = −ξ (signe inversé). Conversion interne.

    Returns
    -------
    np.ndarray  — n maxima annuels simulés (m³/s ou m).
    """
    rng = np.random.default_rng(seed)
    data = stats.genextreme.rvs(-xi, loc=loc, scale=scale, size=n, random_state=rng)
    return np.maximum(data, 0.1)


def compute_annual_max(
    df: pd.DataFrame,
    value_col: str = "resultat_obs",
) -> np.ndarray:
    """
    Extrait les maxima annuels hydrologiques (année sep–août).

    Returns
    -------
    np.ndarray — peut être vide si < 1 an de données.
    """
    if df.empty or "date_obs" not in df.columns or value_col not in df.columns:
        return np.array([])

    df = df.copy()
    df["date_obs"] = pd.to_datetime(df["date_obs"])
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df["hydro_year"] = df["date_obs"].apply(
        lambda d: d.year if d.month >= 9 else d.year - 1
    )
    maxima = df.groupby("hydro_year")[value_col].max().dropna()
    return maxima.values


def compute_annual_max_elab(
    df: pd.DataFrame,
    value_col: str = "resultat_obs_elab",
    date_col: str = "date_obs_elab",
) -> pd.Series:
    """
    Extrait les maxima annuels hydrologiques depuis les observations élaborées (obs_elab).

    Identique à compute_annual_max mais pour les DataFrames obs_elab de Hub'Eau v2
    (colonnes date_obs_elab / resultat_obs_elab).  Année hydrologique : septembre → août.

    Parameters
    ----------
    df : pd.DataFrame
        Retour de load_obs_elab().  Les débits Q doivent déjà être en m³/s
        (la conversion L/s → m³/s est faite dans load_obs_elab).
    value_col : str
        Colonne de valeur (défaut : 'resultat_obs_elab').
    date_col : str
        Colonne de date (défaut : 'date_obs_elab').

    Returns
    -------
    pd.Series  — index = année hydrologique (int), valeurs = maxima annuels.
                 Vide si < 1 an de données.
    """
    if df.empty or date_col not in df.columns or value_col not in df.columns:
        return pd.Series(dtype=float)

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
    df["hydro_year"] = df[date_col].apply(
        lambda d: d.year if d.month >= 9 else d.year - 1
    )
    return df.groupby("hydro_year")[value_col].max().dropna()


# ── Estimateur GEV par L-moments (Hosking & Wallis 1997) ─────────────────────

def _lmom_gev(data: np.ndarray):
    """
    Estimation des paramètres GEV par la méthode des L-moments.

    Beaucoup plus robuste que la MLE pour les petits échantillons (n < 100)
    avec queues lourdes (ξ > 0), situation typique des crues méditerranéennes.

    Référence : Hosking & Wallis (1997), Regional Frequency Analysis.
    Convention retournée : ξ standard (ξ > 0 = Fréchet).

    Returns
    -------
    (xi, loc, scale) : en convention STANDARD.
    """
    n = len(data)
    if n < 5:
        raise ValueError("Pas assez de données pour L-moments GEV (min 5)")

    x = np.sort(data)
    i = np.arange(1, n + 1, dtype=float)

    # Probability Weighted Moments (estimateurs sans biais)
    b0 = x.mean()
    b1 = np.dot(i - 1, x) / (n * (n - 1))
    b2 = np.dot((i - 1) * (i - 2), x) / (n * (n - 1) * (n - 2))

    # L-moments
    l2 = 2.0 * b1 - b0
    l3 = 6.0 * b2 - 6.0 * b1 + b0
    tau3 = l3 / l2  # L-skewness

    # Approximation de Hosking (1997) : ξ ≈ f(τ₃)
    # Valide pour -1/3 < τ₃ < 1  →  correpond à -0.5 < ξ < +∞
    tau3 = float(np.clip(tau3, -0.95, 0.95))
    c = 2.0 / (3.0 + tau3) - np.log(2.0) / np.log(3.0)
    xi = 7.8590 * c + 2.9554 * c ** 2
    xi = float(np.clip(xi, -0.5, 0.6))  # bornes physiques pour données de crues

    if abs(xi) < 1e-6:
        # Cas Gumbel
        scale = float(l2 / np.log(2.0))
        loc   = float(b0 - 0.57721566 * scale)
    else:
        # Formules Hosking (1985) — convention standard ξ
        # λ₂ = σ · Γ(1-ξ) · (1-2^(-ξ)) / ξ
        g1xi  = _gamma(1.0 - xi)
        scale = float(l2 * xi / (g1xi * (1.0 - 2.0 ** (-xi))))
        # λ₁ = μ + σ·(Γ(1-ξ)-1)/ξ
        loc   = float(b0 - scale * (g1xi - 1.0) / xi)

    return xi, loc, scale


# ── Ajustement des distributions ──────────────────────────────────────────────

def _aic(log_likelihood: float, k: int) -> float:
    """Critère d'Akaike : AIC = 2k − 2·ℓ."""
    return 2 * k - 2 * log_likelihood


def fit_distributions(data: np.ndarray) -> dict:
    """
    Ajuste GEV (L-moments), Gumbel (MLE) et Log-Normale (MLE).

    Returns
    -------
    dict  {nom: {params, aic, ks_stat, ks_pvalue, rv, label, color}}
    `rv`  distribution scipy gelée (frozen).
    """
    results = {}
    data = np.asarray(data, dtype=float)
    data = data[np.isfinite(data) & (data > 0)]

    if len(data) < 5:
        return results

    # ── GEV via L-moments (Hosking & Wallis 1997) ────────────────────────────
    # MLE scipy est instable pour ξ > 0 et n < 100 → L-moments beaucoup plus robuste
    try:
        xi, loc, scale = _lmom_gev(data)
        c_scipy = -xi   # convention scipy : c = −ξ
        ll = float(np.sum(stats.genextreme.logpdf(data, c_scipy, loc, scale)))
        ks_stat, ks_p = stats.kstest(data, "genextreme", args=(c_scipy, loc, scale))
        results["GEV"] = {
            "params": {
                "ξ (forme)": round(xi, 4),
                "μ (loc)":   round(loc, 1),
                "σ (scale)": round(scale, 1),
            },
            "aic":       _aic(ll, 3),
            "ks_stat":   float(ks_stat),
            "ks_pvalue": float(ks_p),
            "rv":        stats.genextreme(c_scipy, loc=loc, scale=scale),
            "label":     f"GEV L-mom (ξ={xi:.3f})",
            "color":     "#e63946",
        }
    except Exception:
        pass

    # ── Gumbel MLE (EV1, cas ξ=0 de la GEV) ─────────────────────────────────
    try:
        loc_g, scale_g = stats.gumbel_r.fit(data)
        ll = float(np.sum(stats.gumbel_r.logpdf(data, loc_g, scale_g)))
        ks_stat, ks_p = stats.kstest(data, "gumbel_r", args=(loc_g, scale_g))
        results["Gumbel"] = {
            "params": {
                "μ (loc)":   round(float(loc_g), 1),
                "σ (scale)": round(float(scale_g), 1),
            },
            "aic":       _aic(ll, 2),
            "ks_stat":   float(ks_stat),
            "ks_pvalue": float(ks_p),
            "rv":        stats.gumbel_r(loc_g, scale_g),
            "label":     "Gumbel (EV1)",
            "color":     "#2196F3",
        }
    except Exception:
        pass

    # ── Log-Normale MLE (LN2, loc=0 fixé) ────────────────────────────────────
    try:
        shape_ln, loc_ln, scale_ln = stats.lognorm.fit(data, floc=0)
        ll = float(np.sum(stats.lognorm.logpdf(data, shape_ln, loc_ln, scale_ln)))
        ks_stat, ks_p = stats.kstest(
            data, "lognorm", args=(shape_ln, loc_ln, scale_ln)
        )
        results["LN2"] = {
            "params": {
                "σ_log (shape)": round(float(shape_ln), 4),
                "μ_log":         round(float(np.log(scale_ln)), 4),
            },
            "aic":       _aic(ll, 2),
            "ks_stat":   float(ks_stat),
            "ks_pvalue": float(ks_p),
            "rv":        stats.lognorm(shape_ln, loc_ln, scale_ln),
            "label":     "Log-Normale (LN2)",
            "color":     "#4CAF50",
        }
    except Exception:
        pass

    return results


# ── Bootstrap CI ──────────────────────────────────────────────────────────────

def bootstrap_ci(
    data: np.ndarray,
    dist_name: str,
    return_periods: np.ndarray,
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple:
    """
    Intervalles de confiance Bootstrap (1−alpha) pour les quantiles de retour.

    Pour GEV, utilise les L-moments (robuste).
    Pour Gumbel/LN2, utilise la MLE scipy.

    Returns
    -------
    (lower, upper) : np.ndarray pour chaque période de retour.
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    exceedance_probs = 1.0 / return_periods
    boot_quantiles = np.full((n_bootstrap, len(return_periods)), np.nan)

    if dist_name not in ("GEV", "Gumbel", "LN2"):
        raise ValueError(f"Distribution inconnue : '{dist_name}'")

    for i in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        try:
            if dist_name == "GEV":
                xi_b, loc_b, scale_b = _lmom_gev(sample)
                rv = stats.genextreme(-xi_b, loc=loc_b, scale=scale_b)
            elif dist_name == "Gumbel":
                loc_b, scale_b = stats.gumbel_r.fit(sample)
                rv = stats.gumbel_r(loc_b, scale_b)
            else:  # LN2
                shape_b, loc_b, scale_b = stats.lognorm.fit(sample, floc=0)
                rv = stats.lognorm(shape_b, loc_b, scale_b)

            boot_quantiles[i] = rv.ppf(1 - exceedance_probs)
        except Exception:
            pass

    lower = np.nanpercentile(boot_quantiles, 100 * alpha / 2, axis=0)
    upper = np.nanpercentile(boot_quantiles, 100 * (1 - alpha / 2), axis=0)
    return lower, upper


# ── Quantiles / tableau ────────────────────────────────────────────────────────

def return_level(rv, return_period: float) -> float:
    """Quantile xT correspondant à la période de retour T (années)."""
    return float(rv.ppf(1.0 - 1.0 / return_period))


def build_return_table(fit_results: dict, return_periods=None) -> pd.DataFrame:
    """Tableau croisé des quantiles par distribution et période de retour."""
    if return_periods is None:
        return_periods = [2, 5, 10, 20, 50, 100, 200, 500, 1000]

    rows = []
    for T in return_periods:
        row: dict = {"T (ans)": T}
        for dist_name, res in fit_results.items():
            try:
                q = return_level(res["rv"], T)
                row[f"{dist_name} (m³/s)"] = round(q, 1)
            except Exception:
                row[f"{dist_name} (m³/s)"] = None
        rows.append(row)

    return pd.DataFrame(rows)


# ── Export Excel ───────────────────────────────────────────────────────────────

def create_excel_report(
    station_code: str,
    station_label: str,
    data_source_lbl: str,
    annual_max_series,
    fit_results: dict,
    return_periods=None,
) -> bytes:
    """
    Génère un rapport d'analyse fréquentielle multi-feuilles au format Excel.

    Parameters
    ----------
    annual_max_series : pd.Series (index=année hydro) ou np.ndarray
    fit_results       : dict retourné par fit_distributions()

    Returns
    -------
    bytes — contenu du fichier .xlsx prêt à télécharger.
    """
    import io
    from datetime import datetime

    if return_periods is None:
        return_periods = [2, 5, 10, 20, 50, 100, 200, 500, 1000]

    best_dist = min(fit_results, key=lambda k: fit_results[k]["aic"]) if fit_results else "—"
    n_data    = len(annual_max_series) if hasattr(annual_max_series, "__len__") else "—"

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:

        # ── Feuille 1 : Métadonnées ────────────────────────────────────────────
        meta = pd.DataFrame([
            ("Station",                    f"{station_label} ({station_code})"),
            ("Source des données",         data_source_lbl),
            ("N maxima annuels",           n_data),
            ("Méthode d'ajustement",       "Block Maxima — GEV L-moments (Hosking & Wallis 1997)"),
            ("Intervalles de confiance",   "Bootstrap 95 % (Efron 1979) — 1 000 réplications"),
            ("Meilleure distribution AIC", best_dist),
            ("Date du rapport",            datetime.now().strftime("%Y-%m-%d %H:%M")),
            ("API",                        "Hub'Eau v2 — https://hubeau.eaufrance.fr"),
        ], columns=["Paramètre", "Valeur"])
        meta.to_excel(writer, sheet_name="Métadonnées", index=False)

        # ── Feuille 2 : Maxima annuels ─────────────────────────────────────────
        if hasattr(annual_max_series, "index"):
            am_df = pd.DataFrame({
                "Année hydrologique":  annual_max_series.index.astype(int),
                "Q max annuel (m³/s)": annual_max_series.values.round(2),
            })
        else:
            am_df = pd.DataFrame({
                "Index":               range(1, len(annual_max_series) + 1),
                "Q max annuel (m³/s)": np.round(np.asarray(annual_max_series, dtype=float), 2),
            })
        am_df.to_excel(writer, sheet_name="Maxima_annuels", index=False)

        # ── Feuille 3 : Quantiles de crue ──────────────────────────────────────
        qt_df = build_return_table(fit_results, return_periods)
        qt_df.to_excel(writer, sheet_name="Quantiles", index=False)

        # ── Feuille 4 : Paramètres et tests d'ajustement ───────────────────────
        param_rows = []
        for dist_name, res in fit_results.items():
            row = {
                "Distribution": res["label"],
                "AIC":          round(res["aic"], 2),
                "KS stat":      round(res["ks_stat"], 4),
                "KS p-value":   round(res["ks_pvalue"], 4),
            }
            for k, v in res["params"].items():
                row[k] = round(float(v), 4)
            param_rows.append(row)
        pd.DataFrame(param_rows).to_excel(writer, sheet_name="Paramètres", index=False)

    return buffer.getvalue()
