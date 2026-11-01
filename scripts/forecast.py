"""Fit Model 1 on 1998-2024, forecast 2026, simulate the map.

Writes artifacts/forecast_2026.csv, artifacts/error_model.json, artifacts/sims_2026.npz and
reports/forecast_2026.md. Usage: python -m scripts.forecast
"""

import json
from dataclasses import asdict

import numpy as np
import pandas as pd
import yaml

from scripts.evaluate import load
from senate_forecast.data import races2026
from senate_forecast.evaluate import loyo
from senate_forecast.features import build
from senate_forecast.forecast import errors, model
from senate_forecast.paths import ARTIFACTS, CONFIGS, REPORTS
from senate_forecast.simulate import sim


def fit_2026(cfg):
    hist, _ = load(cfg)
    cycles = sorted(hist["cycle"].unique())
    fund, pe = loyo.fit_point(hist, cfg["features"])
    # error model from leave-one-year-out residuals of the point model
    folds = [([c for c in cycles if c != y], y) for y in cycles]
    oos = loyo.out_of_sample(hist, cfg["features"], folds)
    resid = oos.assign(r=oos["margin_2p"] - oos["mu"])
    rng = np.random.default_rng(cfg["simulation"]["seed"])
    em = errors.fit_error_model(resid, cfg["errors"], rng)
    em_int = em  # scale for the 80% margin ranges (see loyo.interval80)
    if cfg["errors"].get("interval_calibrate") == "coverage" and cfg["errors"].get("calibrate") == "logloss":
        em_int = errors.fit_error_model(resid, {**cfg["errors"], "calibrate": "coverage"}, rng)

    live = build.live_2026()
    ind = set(live.loc[live["poll_col"] == "Ind", "race_id"])
    polls = build.poll_table([2026], ind)
    pavg = model.poll_average(polls, cfg["polls"])
    live = live.merge(pavg, on="race_id", how="left")
    fc = loyo.predict_point(live, fund, pe)
    return fc, fund, pe, em, em_int


if __name__ == "__main__":
    cfg = yaml.safe_load((CONFIGS / "forecast.yaml").read_text())
    fc, fund, pe, em, em_int = fit_2026(cfg)
    sims = sim.simulate(fc, em, cfg["simulation"], cfg["errors"]["extra_sd"])
    o = sims.outcomes()
    out = sims.summary(fc)
    if em_int is not em:  # 80% margin ranges from the coverage-calibrated scale
        wide = sim.simulate(fc, em_int, cfg["simulation"], cfg["errors"]["extra_sd"])
        out["lo80"], out["hi80"] = np.quantile(wide.margin, [0.1, 0.9], axis=0)
    out = out.merge(races2026.consensus().rename_axis("race_id").reset_index(), on="race_id", how="left")

    ARTIFACTS.mkdir(exist_ok=True)
    out.to_csv(ARTIFACTS / "forecast_2026.csv", index=False)
    np.savez_compressed(ARTIFACTS / "sims_2026.npz", race_ids=np.array(sims.race_ids),
                        margin=sims.margin.astype(np.float32), nr_wins=o["nr_wins"], d_seats=o["d_seats"])
    (ARTIFACTS / "error_model.json").write_text(json.dumps({
        **asdict(em), "interval_c": em_int.c, "fundamentals": fund.params.round(4).to_dict(), "sd_a": fund.sd_a,
        "sd_b": fund.sd_b, "sigma_b2": float(pe.sigma_b2), "sigma_s2": float(pe.sigma_s2)}, indent=1))

    show = out.sort_values("p_nr")[["race_id", "cand_nr", "cand_r", "n_polls", "poll_avg", "mu_f",
                                    "mu", "lo80", "hi80", "p_nr", "p_consensus"]]
    seats = pd.Series(o["d_seats"]).value_counts(normalize=True).sort_index()
    lines = ["# 2026 Senate forecast (Model 1)", "",
             f"P(Democrats control the Senate) = **{o['d_control'].mean():.1%}** "
             f"(needs 51 seats; median D+I seats {int(np.median(o['d_seats']))})", "",
             f"Error model: sigma_nat {em.sigma_nat:.2f}, sigma_reg {em.sigma_reg:.2f}, c {em.c:.2f}, t df {em.df}.",
             "p_nr is the model's P(non-Republican wins); p_consensus comes from the 11-rater Wikipedia table "
             "and is not used by the model.", "",
             show.round(3).to_markdown(index=False), "", "## Seat distribution (D+I)", "",
             seats[seats > 0.005].round(3).to_markdown()]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "forecast_2026.md").write_text("\n".join(lines))
    print("\n".join(lines[:5]))
    print(show.round(2).to_string(index=False))
    print(json.dumps(asdict(em)), fund.params.round(3).to_dict(), round(fund.sd_a, 2), round(fund.sd_b, 3), pe)
