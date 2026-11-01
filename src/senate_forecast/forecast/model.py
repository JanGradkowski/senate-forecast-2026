"""Model 1, point forecast: fundamentals prior (A), house-effect poll average (B), precision blend (C).

All margins are the two-party margin of the non-Republican over the Republican, in points.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

# ---------- Stage A: fundamentals ----------

@dataclass
class Fundamentals:
    params: pd.Series
    # Error SD grows with how lopsided the race is: sigma_f = sd_a + sd_b * |mu_f|.
    # In-sample values here; an out-of-fold fit replaces them before use.
    sd_a: float
    sd_b: float = 0.0

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = sm.add_constant(df[self.params.index[1:]], has_constant="add")
        return X.to_numpy() @ self.params.to_numpy()

    def sigma(self, df: pd.DataFrame) -> np.ndarray:
        return self.sd_a + self.sd_b * np.abs(self.predict(df))


def fit_fundamentals(train: pd.DataFrame, features: list[str]) -> Fundamentals:
    """Huber-robust regression: landslides against weak challengers would otherwise dominate.
    Beat OLS on every leave-one-year-out score (log loss 0.1626 vs 0.1635)."""
    X = sm.add_constant(train[features])
    fit = sm.RLM(train["margin_2p"], X, M=sm.robust.norms.HuberT()).fit()
    return Fundamentals(fit.params, float(fit.scale))


def fit_sigma_f(mu_f: np.ndarray, resid: np.ndarray) -> tuple[float, float]:
    """Regress |residual| on |mu_f|; for normal errors E|e| = sigma * sqrt(2/pi)."""
    X = np.c_[np.ones(len(mu_f)), np.abs(mu_f)]
    (a, b), *_ = np.linalg.lstsq(X, np.abs(resid), rcond=None)
    k = np.sqrt(np.pi / 2)
    return max(k * a, 2.0), max(k * b, 0.0)


# ---------- Stage B: poll average with house effects ----------

def poll_weights(p: pd.DataFrame, cfg: dict) -> np.ndarray:
    cutoff = p["election_date"] - pd.Timedelta(days=cfg["cutoff_days"])
    age = (cutoff - p["end_date"]).dt.days.clip(lower=0).to_numpy()
    n = p["n"].fillna(cfg["default_n"]).clip(upper=1500).to_numpy()
    partisan = p["partisan"].notna() & (p["partisan"].astype(str).str.strip() != "")
    w = np.exp(-age / cfg["tau_days"]) * np.sqrt(n / cfg["default_n"])
    return w * np.where(partisan, cfg["partisan_weight"], 1.0)


def poll_average(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per-race poll average for one cycle, net of shrunk pollster house effects.

    Solves  min_w  sum_k w_k (m_k - mu_race(k) - h_pollster(k))^2 + lambda * sum_p h_p^2
    with race terms unpenalised. Returns race_id, poll_avg, n_eff, n_polls, undecided.
    """
    cutoff = p["election_date"] - pd.Timedelta(days=cfg["cutoff_days"])
    p = p[p["end_date"] <= cutoff].copy()
    p = p[(p["pct_nr"] + p["pct_r"]) > 0]
    if p.empty:
        return pd.DataFrame(columns=["race_id", "poll_avg", "n_eff", "n_polls", "undecided"])
    m = 100 * (p["pct_nr"] - p["pct_r"]) / (p["pct_nr"] + p["pct_r"])
    w = poll_weights(p, cfg)
    races = pd.Index(p["race_id"].unique())
    pollsters = pd.Index(p["pollster"].unique())
    ri, pi = races.get_indexer(p["race_id"]), pollsters.get_indexer(p["pollster"])
    k, R, P = len(p), len(races), len(pollsters)
    X = np.zeros((k, R + P))
    X[np.arange(k), ri] = 1
    X[np.arange(k), R + pi] = 1
    pen = np.r_[np.zeros(R), np.full(P, cfg["house_ridge"])]
    A = X.T @ (w[:, None] * X) + np.diag(pen)
    beta = np.linalg.solve(A + 1e-9 * np.eye(R + P), X.T @ (w * m.to_numpy()))
    p["_w"] = w
    g = p.groupby("race_id")
    out = pd.DataFrame({
        "poll_avg": pd.Series(beta[:R], index=races),
        "n_eff": g["_w"].sum() ** 2 / g["_w"].apply(lambda x: (x ** 2).sum()),
        "n_polls": g.size(),
        "undecided": g.apply(lambda d: (100 - d["pct_nr"] - d["pct_r"]).clip(lower=0).mean()),
    })
    # weight-sum below ~0.05 means every poll is months old: treat as effectively unpolled
    out["w_sum"] = g["_w"].sum()
    return out.rename_axis("race_id").reset_index()


# ---------- Stage C: precision blend ----------

@dataclass
class PollError:
    sigma_b2: float  # irreducible race-level poll error variance
    sigma_s2: float  # sampling variance per effective poll


def fit_poll_error(df: pd.DataFrame) -> PollError:
    """Method of moments: E[(poll_avg - actual)^2] = sigma_b^2 + sigma_s^2 / n_eff."""
    d = df.dropna(subset=["poll_avg"])
    e2 = (d["poll_avg"] - d["margin_2p"]) ** 2
    X = np.c_[np.ones(len(d)), 1 / d["n_eff"]]
    coef, *_ = np.linalg.lstsq(X, e2, rcond=None)
    return PollError(max(coef[0], 1.0), max(coef[1], 0.0))


def blend(df: pd.DataFrame, mu_f: np.ndarray, sigma_f: float, pe: PollError) -> pd.DataFrame:
    """Posterior mean and SD of the margin, combining the prior with the poll average."""
    out = df.copy()
    out["mu_f"] = mu_f
    v_poll = pe.sigma_b2 + pe.sigma_s2 / out["n_eff"]
    has = out["poll_avg"].notna() & (out["w_sum"].fillna(0) > 0.05)
    w = np.where(has, sigma_f ** 2 / (sigma_f ** 2 + v_poll.fillna(np.inf)), 0.0)
    out["w_poll"] = w
    out["mu"] = np.where(has, w * out["poll_avg"].fillna(0) + (1 - w) * out["mu_f"], out["mu_f"])
    post_var = np.where(has, 1 / (1 / sigma_f ** 2 + 1 / v_poll.fillna(np.inf)), sigma_f ** 2)
    out["s_post"] = np.sqrt(post_var)
    return out
