"""Leave-one-year-out and forward-chaining validation of Model 1, with baselines and gates."""

import numpy as np
import pandas as pd
from scipy.stats import norm

from senate_forecast.forecast import errors, model


def poll_averages(polls: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Stage B for every cycle. Each cycle uses only its own pre-election polls."""
    return pd.concat([model.poll_average(g, cfg).assign(cycle=c)
                      for c, g in polls.groupby("cycle")], ignore_index=True)


def simple_poll_mean(polls: pd.DataFrame, cutoff_days: int) -> pd.DataFrame:
    """Baseline B1 input: unweighted mean two-party margin of polls in the final 21 days."""
    cutoff = polls["election_date"] - pd.Timedelta(days=cutoff_days)
    p = polls[(polls["end_date"] <= cutoff)
              & (polls["end_date"] >= polls["election_date"] - pd.Timedelta(days=21))]
    m = 100 * (p["pct_nr"] - p["pct_r"]) / (p["pct_nr"] + p["pct_r"])
    return m.groupby([p["cycle"], p["race_id"]]).mean().rename("b1_mean").reset_index()


def _oof_sigma_f(train: pd.DataFrame, features: list[str]) -> tuple[float, float]:
    """Error-SD model of the fundamentals prior, from inner leave-one-year-out residuals."""
    mu, res = [], []
    for y in train["cycle"].unique():
        f = model.fit_fundamentals(train[train["cycle"] != y], features)
        t = train[train["cycle"] == y]
        mu.append(f.predict(t))
        res.append(t["margin_2p"].to_numpy() - mu[-1])
    return model.fit_sigma_f(np.concatenate(mu), np.concatenate(res))


def fit_point(train: pd.DataFrame, features: list[str]):
    """Fit Stage A and the Stage C poll-error parameters on training races."""
    fund = model.fit_fundamentals(train, features)
    fund.sd_a, fund.sd_b = _oof_sigma_f(train, features)
    pe = model.fit_poll_error(train)
    return fund, pe


def predict_point(df: pd.DataFrame, fund, pe) -> pd.DataFrame:
    return model.blend(df, fund.predict(df), fund.sigma(df), pe).assign(sigma_f=fund.sigma(df))


def out_of_sample(hist: pd.DataFrame, features: list[str], folds: list[tuple[list, int]]) -> pd.DataFrame:
    """Point predictions for each test cycle from a model trained on its fold's train cycles."""
    preds = []
    for train_cycles, y in folds:
        train = hist[hist["cycle"].isin(train_cycles)]
        fund, pe = fit_point(train, features)
        preds.append(predict_point(hist[hist["cycle"] == y], fund, pe))
    return pd.concat(preds, ignore_index=True)


COMPETITIVE_MU = 15  # races whose forecast margin is within 15 points enter the joint score


def interval80(g, train, cfg_err, em, draws, n, rng):
    """80% margin range. Win probabilities use the scale calibrated to win/lose log loss, which is
    driven by close races and too narrow for margins (lopsided, unpolled races miss by a lot without
    changing the winner). With `interval_calibrate: coverage` the range comes from a second scale
    fitted, on the same training years, to cover 80% of margins."""
    if cfg_err.get("interval_calibrate") == "coverage" and cfg_err.get("calibrate") == "logloss":
        em_int = errors.fit_error_model(train, {**cfg_err, "calibrate": "coverage"}, rng)
        draws = g["mu"].to_numpy() + errors.predictive_errors(g["s_post"].to_numpy(), g["region"].to_numpy(),
                                                              em_int, n, rng)
    return np.quantile(draws, [0.1, 0.9], axis=0)


def probabilities(pred: pd.DataFrame, cfg_err: dict, seed: int, n: int = 20000) -> pd.DataFrame:
    """Win probabilities and 80% intervals for each held-out cycle; the error model for cycle y
    is fit on the out-of-sample residuals of the other cycles only.

    `count_nll` (one value per cycle) is the joint score: -log P(the observed number of non-R
    wins among races with |mu| < 15). It tests the shared national and regional errors, which
    race-by-race scores cannot see.
    """
    pred = pred.assign(r=pred["margin_2p"] - pred["mu"])
    rng = np.random.default_rng(seed)
    out = []
    for y, g in pred.groupby("cycle"):
        train = pred[pred["cycle"] != y]
        em = errors.fit_error_model(train, cfg_err, rng)
        e = errors.predictive_errors(g["s_post"].to_numpy(), g["region"].to_numpy(), em, n, rng)
        draws = g["mu"].to_numpy() + e
        lo, hi = interval80(g, train, cfg_err, em, draws, n, rng)
        comp = (g["mu"].abs() < COMPETITIVE_MU).to_numpy()
        won = g["nr_won"].to_numpy()[comp].astype(bool)
        count, obs_count = (draws[:, comp] > 0).sum(axis=1), int(won.sum())
        fav = g["mu"].to_numpy()[comp] > 0
        upsets, obs_upsets = ((draws[:, comp] > 0) != fav).sum(axis=1), int((won != fav).sum())
        u = rng.random(2)  # randomised PITs for discrete counts
        out.append(g.assign(p_nr=(draws > 0).mean(axis=0), lo80=lo, hi80=hi,
                            sigma_nat=em.sigma_nat, sigma_reg=em.sigma_reg, c=em.c,
                            count_nll=-np.log((count == obs_count).mean() + 1 / n),
                            count_pit=(count < obs_count).mean() + u[0] * (count == obs_count).mean(),
                            upset_pit=(upsets < obs_upsets).mean() + u[1] * (upsets == obs_upsets).mean()))
    return pd.concat(out, ignore_index=True)


def cycle_scores(prob: pd.DataFrame) -> pd.DataFrame:
    """Per held-out cycle: mean log loss, joint score, and expected vs observed upsets."""
    def one(d):
        p, y = d["p_nr"].to_numpy(), d["nr_won"].astype(float).to_numpy()
        under = np.minimum(p, 1 - p)
        upset = np.where(p < 0.5, y, 1 - y)
        return pd.Series({"n": len(d), "logloss": _logloss(p, y), "count_nll": d["count_nll"].iloc[0],
                          "upsets_expected": under[under < 0.35].sum(),
                          "upsets_observed": upset[under < 0.35].sum()})
    return prob.groupby("cycle").apply(one, include_groups=False)


def _brier(p, y):
    return float(np.mean((p - y) ** 2))


def _logloss(p, y):
    p = np.clip(p, 0.005, 0.995)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _ece(p, y, bins=5):
    idx = np.minimum((p * bins).astype(int), bins - 1)
    df = pd.DataFrame({"b": idx, "p": p, "y": y})
    g = df.groupby("b").agg(n=("y", "size"), p=("p", "mean"), y=("y", "mean"))
    return float((g["n"] * (g["p"] - g["y"]).abs()).sum() / len(df)), g


def score(prob: pd.DataFrame, b1: pd.DataFrame) -> dict:
    """Model vs baselines B1 (polls only, sigma 5) and B2 (fundamentals only)."""
    d = prob.merge(b1, on=["cycle", "race_id"], how="left")
    y = d["nr_won"].astype(float).to_numpy()
    p_b2 = norm.cdf(d["mu_f"] / d["sigma_f"])
    p_b1 = norm.cdf(d["b1_mean"] / 5.0)
    polled = d["b1_mean"].notna().to_numpy()
    lean = np.where(polled, d["b1_mean"], d["mu_f"])
    comp = np.abs(lean) < 10
    ece, bins = _ece(d["p_nr"].to_numpy(), y)
    err, err_f, err_b1 = d["margin_2p"] - d["mu"], d["margin_2p"] - d["mu_f"], d["margin_2p"] - d["b1_mean"]
    s = {
        "n_races": len(d), "n_polled": int(polled.sum()), "n_competitive": int(comp.sum()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "rmse_b2": float(np.sqrt((err_f ** 2).mean())),
        "rmse_polled": float(np.sqrt((err[polled] ** 2).mean())),
        "rmse_b1_polled": float(np.sqrt((err_b1[polled] ** 2).mean())),
        "logloss": _logloss(d["p_nr"].to_numpy(), y),
        "logloss_b2": _logloss(p_b2, y),
        "logloss_polled": _logloss(d["p_nr"].to_numpy()[polled], y[polled]),
        "logloss_b1_polled": _logloss(p_b1[polled], y[polled]),
        "brier": _brier(d["p_nr"].to_numpy(), y),
        "brier_competitive": _brier(d["p_nr"].to_numpy()[comp], y[comp]),
        "brier_b1_competitive": _brier(np.where(polled, p_b1, p_b2)[comp], y[comp]),
        "brier_b2_competitive": _brier(p_b2[comp], y[comp]),
        "coverage80": float(((d["margin_2p"] >= d["lo80"]) & (d["margin_2p"] <= d["hi80"])).mean()),
        "ece": ece,
        "max_bin_gap": float((bins.loc[bins["n"] >= 20, "p"] - bins.loc[bins["n"] >= 20, "y"]).abs().max()),
        "accuracy": float(((d["p_nr"] > 0.5) == (y == 1)).mean()),
    }
    return s


def gates(s: dict) -> dict:
    return {
        "G1 rmse below both baselines": s["rmse"] < s["rmse_b2"] and s["rmse_polled"] < s["rmse_b1_polled"],
        "G2 log loss <= baselines, competitive Brier <= B1":
            s["logloss"] <= s["logloss_b2"] and s["logloss_polled"] <= s["logloss_b1_polled"]
            and s["brier_competitive"] <= s["brier_b1_competitive"],
        "G3 80% coverage in [72,88] and bins within 10pp":
            0.72 <= s["coverage80"] <= 0.88 and s["max_bin_gap"] <= 0.10,
    }
