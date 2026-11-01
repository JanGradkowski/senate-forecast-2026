"""Collect every number the explainer scenes show into video/scenes/data.json.

Nothing is typed in by hand: each value is read from the repository's outputs (gui/data/senate.json,
reports/*.md, reports/model1_loyo_predictions.csv, configs/forecast.yaml, README.md) or computed from
them, and `sources` records where it came from.

Usage (from the repository root):  python video/prepare_data.py
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video" / "scenes" / "data.json"


def md_table(text: str, header_start: str) -> pd.DataFrame:
    """First markdown table whose header row starts with `header_start`."""
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.strip().startswith(header_start))
    rows = []
    for ln in lines[i:]:
        if not ln.strip().startswith("|"):
            break
        rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    head, body = rows[0], [r for r in rows[2:]]
    return pd.DataFrame(body, columns=head)


def yaml_number(text: str, key: str) -> float:
    return float(re.search(rf"^\s*{key}:\s*([0-9.]+)", text, re.M).group(1))


def huber_line(x: np.ndarray, y: np.ndarray, t: float = 1.345, iters: int = 100) -> tuple[float, float]:
    """Huber M-estimate of y = a + b x by IRLS with a MAD scale (statsmodels RLM's defaults)."""
    X = np.c_[np.ones_like(x), x]
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    for _ in range(iters):
        r = y - X @ beta
        s = np.median(np.abs(r)) / 0.6745
        u = np.abs(r / s)
        w = np.where(u <= t, 1.0, t / u)
        new = np.linalg.solve(X.T @ (w[:, None] * X), X.T @ (w * y))
        if np.allclose(new, beta, atol=1e-10):
            break
        beta = new
    return float(beta[0]), float(beta[1])


def main() -> None:
    senate = json.loads((ROOT / "gui/data/senate.json").read_text())
    loyo = pd.read_csv(ROOT / "reports/model1_loyo_predictions.csv")
    validation = (ROOT / "reports/model1_validation.md").read_text()
    forecast_md = (ROOT / "reports/forecast_2026.md").read_text()
    cfg = (ROOT / "configs/forecast.yaml").read_text()
    readme = (ROOT / "README.md").read_text()

    # ---- history: elections, races, polls
    cycles = sorted(int(c) for c in loyo["cycle"].unique())
    by_cycle = []
    for c in cycles:
        d = loyo[loyo["cycle"] == c]
        by_cycle.append({"cycle": c, "nr_won": int(d["nr_won"].sum()), "r_won": int((~d["nr_won"].astype(bool)).sum())})
    history = {
        "n_elections": len(cycles), "first": cycles[0], "last": cycles[-1],
        "n_races": int(len(loyo)),
        "n_polls": int(loyo["n_polls"].fillna(0).sum()),
        "by_cycle": by_cycle,
    }

    # ---- fundamentals scatter: state lean vs actual margin, with a Huber line
    a, b = huber_line(loyo["pres_lean"].to_numpy(float), loyo["margin_2p"].to_numpy(float))
    coef = md_table(readme, "| Feature | Coefficient")
    coef = dict(zip(coef["Feature"], coef["Coefficient"]))
    fundamentals = {
        "points": [[round(float(x), 2), round(float(y), 2)] for x, y in zip(loyo["pres_lean"], loyo["margin_2p"])],
        "huber": {"intercept": a, "slope": b},
        "incumbency_pts": float(coef["Incumbency"].split()[0]),
        "prior_sd": float(re.search(r"prior's error SD \(([0-9.]+) points\)", readme).group(1)),
    }

    # ---- polls and the precision blend (Texas: many polls; Nebraska: few)
    ft = md_table(forecast_md, "| race_id")
    ft = ft.set_index("race_id")
    sf = fundamentals["prior_sd"]
    blend = []
    for rid in ("TX", "NE"):
        r = ft.loc[rid]
        mu_f, poll, mu, n = float(r["mu_f"]), float(r["poll_avg"]), float(r["mu"]), int(float(r["n_polls"]))
        # model: mu = w * poll + (1 - w) * mu_f with w = sf^2 / (sf^2 + v_poll); post var = 1 / (1/sf^2 + 1/v_poll)
        w = (mu - mu_f) / (poll - mu_f)
        v_poll = sf**2 * (1 - w) / w
        race = next(x for x in senate["races"] if x["postal"] == rid)
        blend.append({
            "postal": rid, "state": race["state"], "party_nr": race["nr"]["party"], "n_polls": n,
            "mu_f": mu_f, "poll_avg": poll, "mu": mu,
            "sd_f": sf, "sd_poll": math.sqrt(v_poll), "sd_post": math.sqrt(1 / (1 / sf**2 + 1 / v_poll)),
        })
    polls = {
        "tau_days": yaml_number(cfg, "tau_days"),
        "house_ridge": yaml_number(cfg, "house_ridge"),
        "n_polls_2026": int(sum(r["polls"]["n"] for r in senate["races"])),
        "n_races_2026": len(senate["races"]),
    }

    # ---- error model and the competitive races it moves together
    region = loyo.groupby("state_po")["region"].first().to_dict()
    comp = sorted((r for r in senate["races"] if abs(r["margin"]) < 10), key=lambda r: -r["margin"])
    errors = {
        "sigma_nat": yaml_number(cfg, "sigma_nat_floor"),
        "sigma_reg": yaml_number(cfg, "sigma_reg_floor"),
        "t_df": yaml_number(cfg, "t_df"),
        "races": [{"postal": r["postal"], "state": r["state"], "margin": r["margin"], "party_nr": r["nr"]["party"],
                   "region": region[r["postal"]]} for r in comp],
    }

    # ---- simulations
    dist = senate["seat_distribution"]
    cum, lo, hi = 0.0, None, None
    for d in dist:
        cum += d["p"]
        if lo is None and cum >= 0.10:
            lo = d["seats"]
        if hi is None and cum >= 0.90:
            hi = d["seats"]
    seats = {
        "dist": [d for d in dist if d["p"] >= 0.002],  # same cut as the GUI's histogram
        "n_draws": senate["n_draws"], "majority": senate["majority"], "median": senate["median_nr_seats"],
        "p_control_nr": senate["p_control_nr"],
        "p_tie": next(d["p"] for d in dist if d["seats"] == 50),
        "range80": [lo, hi],
        "not_up": senate["not_up"],
    }

    # ---- validation (leave-one-year-out)
    vt = md_table(validation, "| metric").set_index("metric")
    col = vt.columns[0]
    miss = (loyo["p_nr"] > 0.5) != loyo["nr_won"].astype(bool)
    val = {
        "accuracy": float(vt.loc["accuracy", col]),
        "coverage80": float(vt.loc["coverage80", col]),
        "logloss": float(vt.loc["logloss", col]),
        "logloss_fundamentals": float(vt.loc["logloss_b2", col]),
        "n_races": int(float(vt.loc["n_races", col])),
        "points": [[round(float(m), 2), round(float(y), 2), int(k)] for m, y, k in zip(loyo["mu"], loyo["margin_2p"], miss)],
        "n_miss": int(miss.sum()),
    }

    out = {
        "as_of": senate["as_of"],
        "races": [{"postal": r["postal"], "state": r["state"], "margin": r["margin"]} for r in senate["races"]],
        "history": history, "fundamentals": fundamentals, "polls": polls, "blend": blend,
        "errors": errors, "seats": seats, "validation": val,
        "sources": {
            "history": "reports/model1_loyo_predictions.csv (cycle, nr_won, n_polls)",
            "fundamentals": "reports/model1_loyo_predictions.csv (pres_lean, margin_2p); README.md (coefficients, prior SD)",
            "blend": "reports/forecast_2026.md (mu_f, poll_avg, mu, n_polls); widths from the blend formula in src/senate_forecast/forecast/model.py",
            "polls": "configs/forecast.yaml (tau_days, house_ridge); gui/data/senate.json (polls.n)",
            "errors": "configs/forecast.yaml (sigma_nat_floor, sigma_reg_floor, t_df); gui/data/senate.json (margins)",
            "seats": "gui/data/senate.json (seat_distribution, p_control_nr, median_nr_seats, n_draws, not_up)",
            "validation": "reports/model1_validation.md (LOYO column); reports/model1_loyo_predictions.csv (mu, margin_2p, p_nr, nr_won)",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1e3:.0f} kB)")
    print(f"  history: {history['n_elections']} elections, {history['n_races']} races, {history['n_polls']} polls")
    print(f"  huber: margin = {a:.2f} + {b:.3f} x lean")
    for x in blend:
        print(f"  blend {x['postal']}: f {x['mu_f']:.2f}, polls {x['poll_avg']:.2f} ({x['n_polls']}), blend {x['mu']:.2f}; "
              f"sd {x['sd_f']:.1f}/{x['sd_poll']:.2f}/{x['sd_post']:.2f}")
    print(f"  seats: P(control) {seats['p_control_nr']}, tie {seats['p_tie']}, 80% range {lo}-{hi}, median {seats['median']}")
    print(f"  validation: acc {val['accuracy']}, cov {val['coverage80']}, ll {val['logloss']} vs {val['logloss_fundamentals']}, misses {val['n_miss']}")
    print(f"  competitive races: {[r['postal'] for r in errors['races']]}")


if __name__ == "__main__":
    main()
