"""Tune Model 1 without overfitting: grid searches scored leave-one-year-out, nested selection.

Stage 1, point model: poll recency (tau_days) x house-effect shrinkage (house_ridge).
Stage 2, error model: tail weight (t_df) x national-error floor x how c is calibrated.
Stage 3, polling bias: shift each year's forecasts by lam x the mean error of *earlier* years.

Every candidate gets per-year out-of-sample scores (race log loss; joint score = -log P(observed
number of non-R wins among competitive races)). The tuned *procedure* is then scored by nested
selection: for each year, pick the candidate that did best on the other years and score that
pick on the held-out year. A stage changes the config only if
  1. the nested score beats the current config's score, and
  2. among candidates within one standard error of the best, the one closest to the current
     config is taken (fewest changed settings), and
  3. the pick's joint score is no worse than the current config's by more than one SE.

Writes reports/model1_tuning.md and artifacts/tune/. Usage: python -W ignore -m scripts.tune_model1
"""

import itertools
import json
import time

import numpy as np
import pandas as pd
import yaml

from senate_forecast.evaluate import loyo
from senate_forecast.features import build
from senate_forecast.paths import ARTIFACTS, CONFIGS, REPORTS

TUNE = ARTIFACTS / "tune"
POINT_GRID = {"tau_days": [7, 14, 28], "house_ridge": [5, 20, 80]}
ERROR_GRID = {"t_df": [4, 5, 10, 30], "sigma_nat_floor": [2.0, 2.5, 3.0, 3.5],
              "calibrate": ["coverage", "logloss"]}
BIAS_LAMBDA = [0.0, 0.25, 0.5, 1.0]
BIAS_FROM = 2004  # bias variants are scored on years with at least three earlier years


def grid(spec: dict) -> list[dict]:
    return [dict(zip(spec, v)) for v in itertools.product(*spec.values())]


def label(d: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in d.items())


def current_label(cands: dict[str, dict], cfg_values: dict) -> str:
    """The candidate equal to the config in use (compared by value: 20 == 20.0)."""
    hit = [k for k, c in cands.items() if all(c[p] == cfg_values[p] for p in c)]
    if not hit:
        raise SystemExit(f"the current config {cfg_values} is not in the grid")
    return hit[0]


def wmean(cs: pd.DataFrame, col: str = "logloss", years=None) -> float:
    d = cs if years is None else cs.loc[cs.index.isin(years)]
    return float(np.average(d[col], weights=d["n"]))


def paired(a: pd.DataFrame, b: pd.DataFrame, col: str = "logloss") -> tuple[float, float]:
    """Race-weighted mean of a - b over years, and its standard error across years."""
    w = a["n"] / a["n"].sum()
    d = (a[col] - b[col]).to_numpy()
    mean = float(np.sum(w * d))
    se = float(np.sqrt(np.sum(w ** 2 * (d - mean) ** 2) * len(d) / max(len(d) - 1, 1)))
    return mean, se


def nested(scores: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Per held-out year: the candidate best on the other years, scored on that year."""
    years = next(iter(scores.values())).index
    rows, picks = [], {}
    for y in years:
        others = [c for c in years if c != y]
        pick = min(scores, key=lambda k: wmean(scores[k], years=others))
        picks[y] = pick
        rows.append(scores[pick].loc[y])
    return pd.DataFrame(rows, index=years), picks


def choose(scores: dict[str, pd.DataFrame], cands: dict[str, dict], current: str) -> tuple[str, pd.DataFrame]:
    """One-SE rule toward the current config, plus the joint-score guard."""
    best = min(scores, key=lambda k: wmean(scores[k]))
    table = []
    for k, cs in scores.items():
        d, se = paired(cs, scores[best])
        dj, sej = paired(cs, scores[current], "count_nll")
        changed = sum(cands[k][p] != cands[current][p] for p in cands[k])
        table.append({"candidate": k, "logloss": wmean(cs), "vs_best": d, "se": se,
                      "joint": float(cs["count_nll"].mean()), "joint_vs_current": dj, "joint_se": sej,
                      "upsets_exp": cs["upsets_expected"].sum(), "upsets_obs": cs["upsets_observed"].sum(),
                      "changed": changed})
    t = pd.DataFrame(table).sort_values("logloss")
    ok = t[(t["vs_best"] <= t["se"]) & (t["joint_vs_current"] <= t["joint_se"])]
    pick = ok.sort_values(["changed", "logloss"]).iloc[0]["candidate"] if len(ok) else current
    return pick, t


def stage(name, cands: dict[str, dict], score_fn, current: str, log: list):
    t0 = time.time()
    scores = {}
    for k, c in cands.items():
        scores[k] = score_fn(c)
        print(f"  {name}: {k}  logloss {wmean(scores[k]):.4f}  joint {scores[k]['count_nll'].mean():.3f}"
              f"  ({time.time() - t0:.0f}s)", flush=True)
    nest, picks = nested(scores)
    dn, sen = paired(nest, scores[current])
    pick, table = choose(scores, cands, current)
    adopt = pick != current and dn < 0
    log += [f"## {name}", "",
            f"Current: `{current}`. Nested (tuned procedure, scored on years it did not tune on): "
            f"log loss {wmean(nest):.4f} vs current {wmean(scores[current]):.4f} "
            f"(difference {dn:+.4f} ± {sen:.4f}).",
            f"One-SE pick on all years: `{pick}`. **{'Adopted' if adopt else 'Kept the current config'}.**", "",
            "Nested picks by held-out year: " + ", ".join(f"{y}: `{p}`" for y, p in picks.items()), "",
            table.round(4).to_markdown(index=False), ""]
    pd.concat(scores, names=["candidate"]).to_csv(TUNE / f"{name.split(':')[0].replace(' ', '_')}.csv")
    return (pick if adopt else current), scores


def main():
    cfg = yaml.safe_load((CONFIGS / "forecast.yaml").read_text())
    TUNE.mkdir(parents=True, exist_ok=True)
    cycles = cfg["train_cycles"]
    hist0 = build.history(cycles)
    polls = build.match_candidates(build.poll_table(cycles, set()), hist0)
    years = sorted(hist0["cycle"].unique())
    folds = [([c for c in years if c != y], y) for y in years]
    seed = cfg["simulation"]["seed"]
    log = ["# Model 1 tuning", "",
           "Grid searches scored leave-one-year-out on 1998-2024 (see scripts/tune_model1.py for the rules).",
           "`logloss` is the race-weighted mean over held-out years; `joint` the mean per-year "
           "-log P(observed count of non-R wins among races within 15 points); `upsets_exp/obs` "
           "count underdog wins (forecast below 35%).", ""]

    preds = {}

    def point_pred(p):
        key = label(p)
        if key not in preds:
            path = TUNE / f"pred_{key.replace(' ', '_').replace('=', '')}.parquet"
            if path.exists():
                preds[key] = pd.read_parquet(path)
            else:
                pavg = loyo.poll_averages(polls, {**cfg["polls"], **p})
                hist = hist0.merge(pavg, on=["cycle", "race_id"], how="left")
                preds[key] = loyo.out_of_sample(hist, cfg["features"], folds)
                preds[key].to_parquet(path)
        return preds[key]

    # stage 1: point model, under the current error model
    pc = {k: cfg["polls"][k] for k in POINT_GRID}
    cands = {label(p): p for p in grid(POINT_GRID)}
    point, _ = stage("Stage 1: poll averaging", cands,
                     lambda p: loyo.cycle_scores(loyo.probabilities(point_pred(p), cfg["errors"], seed)),
                     current_label(cands, pc), log)
    pred = point_pred(cands[point])

    # stage 2: error model
    ec = {k: cfg["errors"].get(k, "coverage") for k in ERROR_GRID}
    cands_e = {label(e): e for e in grid(ERROR_GRID)}
    err, _ = stage("Stage 2: error model", cands_e,
                   lambda e: loyo.cycle_scores(loyo.probabilities(pred, {**cfg["errors"], **e}, seed)),
                   current_label(cands_e, ec), log)
    err_cfg = {**cfg["errors"], **cands_e[err]}

    # stage 3: polling-bias correction from earlier years only
    def biased(lam):
        r = pred.assign(err=pred["margin_2p"] - pred["mu"], w=1 / pred["s_post"] ** 2)
        comp = r[r["mu"].abs() < loyo.COMPETITIVE_MU]
        yearly = comp.groupby("cycle").apply(lambda d: np.average(d["err"], weights=d["w"]), include_groups=False)
        shift = {y: lam * yearly[yearly.index < y].mean() if (yearly.index < y).any() else 0.0 for y in years}
        p = pred.assign(mu=pred["mu"] + pred["cycle"].map(shift))
        cs = loyo.cycle_scores(loyo.probabilities(p, err_cfg, seed))
        return cs[cs.index >= BIAS_FROM]

    cands_b = {f"lam={lam}": {"lam": lam} for lam in BIAS_LAMBDA}
    bias, _ = stage("Stage 3: polling bias", cands_b, lambda b: biased(b["lam"]), "lam=0.0", log)

    result = {"polls": cands[point], "errors": cands_e[err], "bias_lambda": cands_b[bias]["lam"]}
    log += ["## Result", "", "```json", json.dumps(result, indent=1), "```"]
    (REPORTS / "model1_tuning.md").write_text("\n".join(log))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
