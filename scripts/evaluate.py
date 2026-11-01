"""Validate Model 1 (LOYO + forward chaining) and write reports/model1_validation.md.

Usage: python -m scripts.evaluate
"""

import json

import matplotlib
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from senate_forecast.evaluate import loyo
from senate_forecast.features import build
from senate_forecast.paths import CONFIGS, PROCESSED, REPORTS


def load(cfg):
    cycles = cfg["train_cycles"]
    hist = build.history(cycles)
    polls = build.match_candidates(build.poll_table(cycles, set()), hist)
    pavg = loyo.poll_averages(polls, cfg["polls"])
    hist = hist.merge(pavg, on=["cycle", "race_id"], how="left")
    b1 = loyo.simple_poll_mean(polls, cfg["polls"]["cutoff_days"])
    return hist, b1


def run(cfg, hist, b1, folds, name):
    pred = loyo.out_of_sample(hist, cfg["features"], folds)
    prob = loyo.probabilities(pred, cfg["errors"], cfg["simulation"]["seed"])
    s = loyo.score(prob, b1)
    return prob, s, loyo.gates(s)


def calibration_plot(prob, path):
    p, y = prob["p_nr"].to_numpy(), prob["nr_won"].astype(float).to_numpy()
    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    g = pd.DataFrame({"b": idx, "p": p, "y": y}).groupby("b").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color="#999", lw=1)
    ax.scatter(g["p"], g["y"], s=g["n"] * 3, color="#3366aa")
    ax.set_xlabel("forecast P(non-R wins)")
    ax.set_ylabel("observed frequency")
    ax.set_title("Leave-one-year-out calibration, 1998-2024")
    fig.tight_layout()
    fig.savefig(path, dpi=120)


if __name__ == "__main__":
    cfg = yaml.safe_load((CONFIGS / "forecast.yaml").read_text())
    hist, b1 = load(cfg)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    hist.to_parquet(PROCESSED / "history.parquet")
    cycles = sorted(hist["cycle"].unique())

    loyo_folds = [([c for c in cycles if c != y], y) for y in cycles]
    fwd_folds = [([c for c in cycles if c < y], y) for y in cycles if y >= 2018]
    prob, s, g = run(cfg, hist, b1, loyo_folds, "loyo")
    prob_f, s_f, g_f = run(cfg, hist, b1, fwd_folds, "forward")

    REPORTS.mkdir(exist_ok=True)
    prob.to_csv(REPORTS / "model1_loyo_predictions.csv", index=False)
    calibration_plot(prob, REPORTS / "model1_calibration.png")
    by_cycle = prob.groupby("cycle").apply(lambda d: pd.Series({
        "races": len(d), "mean_err": (d["margin_2p"] - d["mu"]).mean(),
        "rmse": np.sqrt(((d["margin_2p"] - d["mu"]) ** 2).mean()),
        "misses": int(((d["p_nr"] > 0.5) != d["nr_won"]).sum()),
        "sigma_nat": d["sigma_nat"].iloc[0], "c": d["c"].iloc[0]}), include_groups=False)

    lines = ["# Model 1 validation", "",
             "Out-of-sample: every number below comes from a model that never saw the scored year.", "",
             "| metric | leave-one-year-out (1998-2024) | forward chaining (2018-2024) |", "|---|---|---|"]
    lines += [f"| {k} | {s[k]:.4g} | {s_f[k]:.4g} |" for k in s]
    lines += ["", "## Gates", "", "| gate | LOYO | forward |", "|---|---|---|"]
    lines += [f"| {k} | {'PASS' if g[k] else 'FAIL'} | {'PASS' if g_f[k] else 'FAIL'} |" for k in g]
    _, bins = loyo._ece(prob["p_nr"].to_numpy(), prob["nr_won"].astype(float).to_numpy())
    bins = bins.assign(gap=bins["p"] - bins["y"], se=np.sqrt(bins["p"] * (1 - bins["p"]) / bins["n"]))
    off = bins[(bins["gap"].abs() > 2 * bins["se"])]
    note = ("No bin is off by more than two standard errors." if off.empty else
            "Bins off by more than two standard errors: " + ", ".join(
                f"forecast {r.p:.1%} vs observed {r.y:.1%} (n={r.n})" for r in off.itertuples()) + ".")
    lines += ["", "## Reliability bins (LOYO)", "",
              "A bin's gap is only meaningful relative to its sampling error `se` (from the forecast probability).", "",
              bins.round(3).to_markdown(), "", note,
              "", "## By cycle (LOYO)", "", by_cycle.round(2).to_markdown(), "",
              "![calibration](model1_calibration.png)"]
    (REPORTS / "model1_validation.md").write_text("\n".join(lines))
    print(json.dumps({"loyo": s, "forward": s_f}, indent=1))
    print(g, g_f, sep="\n")
    print(by_cycle.round(2))
