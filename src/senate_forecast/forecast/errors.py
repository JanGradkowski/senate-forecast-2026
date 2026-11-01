"""Model 1, uncertainty: national + regional + race-level Student-t errors, calibrated out of sample."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

REGIONS = ["Northeast", "Midwest", "South", "West"]


@dataclass
class ErrorModel:
    sigma_nat: float
    sigma_reg: float
    c: float          # race-level SD = c * s_post (posterior SD from the precision blend)
    df: int


def unit_t(rng, df, size):
    """Student-t draws rescaled to unit variance."""
    return rng.standard_t(df, size) / np.sqrt(df / (df - 2))


def _weighted_group_means(r, w, keys):
    g = pd.DataFrame({"r": r, "w": w, "k": keys}).groupby("k")
    sw = g["w"].sum()
    mean = g.apply(lambda d: np.average(d["r"], weights=d["w"]), include_groups=False)
    return mean, 1 / sw  # mean and its sampling variance if only race-level noise existed


def fit_components(resid: pd.DataFrame, floor: float) -> tuple[float, float]:
    """Shared-cycle and cycle-by-region SDs of out-of-sample residuals (column `r`).

    Method of moments on precision-weighted group means: landslide races have huge but
    irrelevant errors, so each race is weighted by 1 / s_post^2. Var(cycle mean) minus its
    sampling variance estimates sigma_nat^2; the same on region-within-cycle means (after
    removing the cycle mean) estimates sigma_reg^2.
    """
    r, w = resid["r"].to_numpy(), 1 / resid["s_post"].to_numpy() ** 2
    # scale weights so 1/sum(w) is in residual units: race-level variance ~ k * s_post^2
    k = np.average(r ** 2, weights=w) * np.mean(w)
    cyc_mean, cyc_var = _weighted_group_means(r, w / k, resid["cycle"].to_numpy())
    sigma_nat2 = np.var(cyc_mean, ddof=1) - np.mean(cyc_var)
    r2 = r - resid["cycle"].map(cyc_mean).to_numpy()
    key = resid["cycle"].astype(str) + resid["region"]
    reg_mean, reg_var = _weighted_group_means(r2, w / k, key.to_numpy())
    sigma_reg2 = np.var(reg_mean, ddof=1) - np.mean(reg_var)
    return max(float(np.sqrt(max(sigma_nat2, 0))), floor), float(np.sqrt(max(sigma_reg2, 0)))


def predictive_errors(s_post: np.ndarray, region: np.ndarray, em: ErrorModel, n: int, rng,
                      extra: np.ndarray | None = None) -> np.ndarray:
    """(n, races) error draws sharing one national shock and one shock per region per draw."""
    nat = unit_t(rng, em.df, (n, 1))
    reg = unit_t(rng, em.df, (n, len(REGIONS)))
    ridx = np.array([REGIONS.index(r) for r in region])
    sd_i = em.c * s_post * (1 if extra is None else extra)
    return em.sigma_nat * nat + em.sigma_reg * reg[:, ridx] + sd_i * unit_t(rng, em.df, (n, len(s_post)))


def fit_c(resid: pd.DataFrame, sigma_nat: float, sigma_reg: float, df: int, target: float,
          rng, n: int = 4000) -> float:
    """Scale c so that central `target` intervals cover `target` of the residuals."""
    lo_q, hi_q = (1 - target) / 2, (1 + target) / 2
    z = {k: unit_t(rng, df, (n, len(resid))) for k in ("nat", "reg", "idio")}
    r, s = resid["r"].to_numpy(), resid["s_post"].to_numpy()

    def coverage(c):
        e = sigma_nat * z["nat"][:, :1] + sigma_reg * z["reg"] + c * s * z["idio"]
        lo, hi = np.quantile(e, [lo_q, hi_q], axis=0)
        return np.mean((r >= lo) & (r <= hi))

    a, b = 0.2, 4.0
    for _ in range(30):
        mid = (a + b) / 2
        a, b = (mid, b) if coverage(mid) < target else (a, mid)
    return (a + b) / 2


C_GRID = np.linspace(0.3, 2.0, 35)


def fit_c_logloss(resid: pd.DataFrame, sigma_nat: float, sigma_reg: float, df: int, rng,
                  n: int = 4000, grid: np.ndarray = C_GRID) -> float:
    """Scale c to minimise the log loss of win/lose outcomes (needs columns mu, nr_won).

    Coverage calibration fixes one quantile of the error distribution; this fits the part that
    decides win probabilities, the CDF at -mu, which is where the tails were too wide.
    """
    z = {k: unit_t(rng, df, (n, len(resid))) for k in ("nat", "reg", "idio")}
    mu, s = resid["mu"].to_numpy(), resid["s_post"].to_numpy()
    y = resid["nr_won"].astype(float).to_numpy()
    shared = sigma_nat * z["nat"][:, :1] + sigma_reg * z["reg"]

    def loss(c):
        p = np.clip(((mu + shared + c * s * z["idio"]) > 0).mean(axis=0), 0.002, 0.998)
        return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))

    return float(grid[np.argmin([loss(c) for c in grid])])


def fit_error_model(resid: pd.DataFrame, cfg: dict, rng) -> ErrorModel:
    sn, sr = fit_components(resid, cfg["sigma_nat_floor"])
    sr = max(sr, cfg.get("sigma_reg_floor", 0.0))
    if cfg.get("calibrate", "coverage") == "logloss":
        c = fit_c_logloss(resid, sn, sr, cfg["t_df"], rng)
    else:
        c = fit_c(resid, sn, sr, cfg["t_df"], cfg["target_coverage"], rng)
    return ErrorModel(sn, sr, c, cfg["t_df"])
