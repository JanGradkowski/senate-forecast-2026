"""Score the 2026 forecast against the actual results.

Usage:
    python -W ignore -m scripts.results_2026 [--refresh [--page PATH]]

--refresh re-parses the results from a saved copy of Wikipedia's "2026 United States Senate elections"
page (default data/raw/wikipedia/2026_senate.html, which scripts.ingest downloads) into
data/external/results_2026.csv. Without it, the committed CSV is scored.

Inputs: the forecast as published on the map (gui/data/senate.json), the fundamentals-only margins in
reports/forecast_2026.md, and the leave-one-year-out backtest (reports/model1_loyo_predictions.csv) for
context. Writes reports/scorecard_2026.md and gui/data/results.json, which the map's Results view reads.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from senate_forecast.data.results2026 import parse_wikipedia
from senate_forecast.evaluate.loyo import _brier, _logloss
from senate_forecast.paths import EXTERNAL, RAW, REPORTS, ROOT

RESULTS = EXTERNAL / "results_2026.csv"
SENATE = ROOT / "gui" / "data" / "senate.json"
GUI_OUT = ROOT / "gui" / "data" / "results.json"
REPORT = REPORTS / "scorecard_2026.md"
PAGE_URL = "https://en.wikipedia.org/w/index.php?title=2026_United_States_Senate_elections&oldid={rev}"


# ---------------------------------------------------------------------------------------------- inputs

def refresh(page: Path) -> pd.DataFrame:
    text = page.read_text(encoding="utf-8")
    rev = re.search(r'"wgRevisionId":(\d+)', text).group(1)
    edited = re.search(r"This page was last edited on ([^,<]+)", text).group(1).strip()
    races = pd.read_csv(EXTERNAL / "races_2026.csv")
    df = parse_wikipedia(text, races, source=f"Wikipedia revision {rev} (last edited {edited})")
    df.to_csv(RESULTS, index=False)
    return df


def md_table(text: str, header_start: str) -> pd.DataFrame:
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.strip().startswith(header_start))
    rows = []
    for ln in lines[i:]:
        if not ln.strip().startswith("|"):
            break
        rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    return pd.DataFrame(rows[2:], columns=rows[0])


def forecast() -> tuple[pd.DataFrame, dict]:
    senate = json.loads(SENATE.read_text())
    fc = pd.DataFrame([{
        "race_id": r["race_id"], "state": r["state"], "nr_party": r["nr"]["party"], "cand_nr": r["nr"]["name"],
        "cand_r": r["r"]["name"], "margin": r["margin"], "lo80": r["lo80"], "hi80": r["hi80"], "p_nr": r["p_nr"],
        "p_consensus": r["p_consensus"], "n_polls": r["polls"]["n"], "poll_avg": r["polls"]["avg"],
    } for r in senate["races"]])
    f = md_table((REPORTS / "forecast_2026.md").read_text(), "| race_id")
    fc = fc.merge(f[["race_id", "mu_f"]].astype({"mu_f": float}), on="race_id")
    return fc, senate


# ---------------------------------------------------------------------------------------------- scoring

def label(m: float, party: str) -> str:
    """The map's margin label: "D +4.2", "I +1.3", "R +9.2"."""
    return "Even" if abs(m) < 0.05 else f"{party if m > 0 else 'R'} +{abs(m):.1f}"


def backtest_years() -> pd.DataFrame:
    """The 14 held-out years, scored the same way as 2026."""
    d = pd.read_csv(REPORTS / "model1_loyo_predictions.csv")
    rows = []
    for cyc, g in d.groupby("cycle"):
        p, y = g["p_nr"].to_numpy(), g["nr_won"].astype(float).to_numpy()
        err = g["margin_2p"] - g["mu"]
        rows.append({"cycle": int(cyc), "n": len(g), "accuracy": float(((p > 0.5) == (y == 1)).mean()),
                     "brier": _brier(p, y), "logloss": _logloss(p, y),
                     "coverage80": float(((g["margin_2p"] >= g["lo80"]) & (g["margin_2p"] <= g["hi80"])).mean()),
                     "bias": float(err.mean())})
    return pd.DataFrame(rows)


def score(d: pd.DataFrame, senate: dict) -> dict:
    p, y = d["p_nr"].to_numpy(), (d["winner"] == "nr").astype(float).to_numpy()
    pc = d["p_consensus"].to_numpy()
    fav = np.where(p >= 0.5, 1.0, 0.0)
    rep = d[d["status"] == "reported"]
    err = rep["actual"] - rep["margin"]
    polled = rep[rep["n_polls"] > 0]
    nr_seats = senate["not_up"]["nr"] + int(y.sum())
    dist = pd.DataFrame(senate["seat_distribution"])
    p_ge = float(dist.loc[dist["seats"] >= nr_seats, "p"].sum())
    p_eq = float(dist.loc[dist["seats"] == nr_seats, "p"].sum())
    cum = dist["p"].cumsum()
    lo80 = int(dist["seats"][cum >= 0.10].iloc[0])
    hi80 = int(dist["seats"][cum >= 0.90].iloc[0])
    under = np.minimum(p, 1 - p)
    # each race's share of the log loss (same clipping as _logloss)
    pcl = np.clip(p, 0.005, 0.995)
    terms = -(y * np.log(pcl) + (1 - y) * np.log(1 - pcl))
    worst = int(np.argmax(terms))
    keep = np.arange(len(d)) != worst
    dem, ind = rep[rep["nr_party"] == "D"], rep[rep["nr_party"] == "I"]
    assumed_nr = int(((d["status"] == "assumed") & (d["winner"] == "nr")).sum())
    s = {
        "n": len(d), "n_reported": len(rep), "n_assumed": int((d["status"] == "assumed").sum()),
        "calls": int((fav == y).sum()),
        "brier": _brier(p, y), "brier_consensus": _brier(pc, y), "brier_coinflip": 0.25,
        "logloss": _logloss(p, y), "logloss_consensus": _logloss(pc, y), "logloss_coinflip": float(np.log(2)),
        "upsets_expected": float(under.sum()), "upsets_observed": int((fav != y).sum()),
        "bias": float(err.mean()), "mae": float(err.abs().mean()), "rmse": float(np.sqrt((err**2).mean())),
        "toward_nr": int((err > 0).sum()),
        "coverage80": float(((rep["actual"] >= rep["lo80"]) & (rep["actual"] <= rep["hi80"])).mean()),
        "covered": int(((rep["actual"] >= rep["lo80"]) & (rep["actual"] <= rep["hi80"])).sum()),
        "rmse_polled_blend": float(np.sqrt(((polled["actual"] - polled["margin"]) ** 2).mean())),
        "rmse_polled_polls": float(np.sqrt(((polled["actual"] - polled["poll_avg"]) ** 2).mean())),
        "rmse_polled_fundamentals": float(np.sqrt(((polled["actual"] - polled["mu_f"]) ** 2).mean())),
        "n_polled": len(polled),
        "bias_polled_polls": float((polled["actual"] - polled["poll_avg"]).mean()),
        "nr_seats": nr_seats, "r_seats": 100 - nr_seats, "control_nr": nr_seats >= senate["majority"],
        "p_control_nr": senate["p_control_nr"], "median_nr_seats": senate["median_nr_seats"],
        "range80": [lo80, hi80], "p_seats_ge": p_ge, "p_seats_eq": p_eq,
        "seats_pit": float(dist.loc[dist["seats"] < nr_seats, "p"].sum() + 0.5 * p_eq),
        "nr_seats_reported_only": nr_seats - assumed_nr,
        "worst_race": d["state"].iloc[worst], "worst_p_winner": float(p[worst] if y[worst] else 1 - p[worst]),
        "worst_consensus_p_winner": float(pc[worst] if y[worst] else 1 - pc[worst]),
        "worst_logloss_share": float(terms[worst] / terms.sum()),
        "logloss_without_worst": _logloss(p[keep], y[keep]), "logloss_consensus_without_worst": _logloss(pc[keep], y[keep]),
        "n_dem": len(dem), "dem_toward": int((dem["actual"] > dem["margin"]).sum()),
        "dem_bias": float((dem["actual"] - dem["margin"]).mean()),
        "ind_errors": {r["state"]: round(float(r["actual"] - r["margin"]), 1) for _, r in ind.iterrows()},
    }
    return s


# ---------------------------------------------------------------------------------------------- outputs

def report(d: pd.DataFrame, s: dict, years: pd.DataFrame, source: str) -> str:
    def f(x, nd=3):
        return f"{x:.{nd}f}"
    rank = lambda col, v, low=True: 1 + int((years[col] < v).sum() if low else (years[col] > v).sum())
    L = ["# 2026 forecast scorecard", "",
         f"The forecast of {json.loads(SENATE.read_text())['as_of']} scored against the results. Results are "
         f"unofficial: {source}. Margins are two-party, non-Republican minus Republican, in points.", ""]
    for _, r in d[d["status"] != "reported"].iterrows():
        L.append(f"- **{r['state']}:** {r['note']}. It counts in the win/loss scores and the seat total, "
                 "but has no margin.")
    L += ["", "## Summary", "",
          f"- **Control:** the forecast gave Democrats + independents an {s['p_control_nr']:.0%} chance of control. "
          f"They won it, {s['nr_seats']}–{s['r_seats']}.",
          f"- **Seats:** {s['nr_seats']} Democratic + independent seats, against a forecast median of "
          f"{s['median_nr_seats']} and an 80% range of {s['range80'][0]}–{s['range80'][1]}. The forecast gave "
          f"{s['nr_seats']} or more seats a {s['p_seats_ge']:.1%} chance. The result sits at the "
          f"{s['seats_pit']:.0%} point of the seat distribution. Without the Alaska assumption the count is "
          f"{s['nr_seats_reported_only']}, the top of the 80% range.",
          f"- **Winners:** the favourite won {s['calls']} of {s['n']} races. The forecast expected "
          f"{s['upsets_expected']:.1f} upsets; {s['upsets_observed']} happened.",
          f"- **Margins:** Democrats and independents beat their projected margin in {s['toward_nr']} of "
          f"{s['n_reported']} races. The average error was {s['bias']:+.1f} points toward them; the typical "
          f"miss was {s['mae']:.1f} points (RMSE {s['rmse']:.1f}). Democrats beat their projection in "
          f"{s['dem_toward']} of {s['n_dem']} races (on average by {s['dem_bias']:+.1f}). Of the "
          f"{len(s['ind_errors'])} independents, {sum(v < 0 for v in s['ind_errors'].values())} fell short of their "
          "projection (" + ", ".join(f"{k} {v:+.1f}" for k, v in sorted(s['ind_errors'].items(), key=lambda kv: kv[1])) + ").",
          f"- **80% ranges:** {s['covered']} of {s['n_reported']} results ({s['coverage80']:.0%}) fell inside "
          "their 80% range.", "",
          "## Scores", "",
          "| | Brier (lower is better) | Log loss (lower is better) |", "|---|---|---|",
          f"| Model | **{f(s['brier'])}** | **{f(s['logloss'])}** |",
          f"| Forecaster ratings consensus (not used by the model) | {f(s['brier_consensus'])} | {f(s['logloss_consensus'])} |",
          f"| Coin flip | {f(s['brier_coinflip'])} | {f(s['logloss_coinflip'])} |", "",
          "Probabilities are clipped to 0.5–99.5% for log loss, as in the backtest.", "",
          f"One race dominates: the model gave {s['worst_race']}'s winner {s['worst_p_winner']:.1%} (the ratings "
          f"consensus {s['worst_consensus_p_winner']:.1%}), and that race alone is {s['worst_logloss_share']:.0%} of "
          f"the model's log loss. Without it, the model scores {s['logloss_without_worst']:.3f} against the "
          f"consensus's {s['logloss_consensus_without_worst']:.3f}.", "",
          "## Against the 14 backtest years", "",
          "The same scores for each year of the leave-one-year-out validation, with 2026 ranked among the "
          "15 years.", "",
          "| | 2026 | Backtest mean | Backtest range | 2026 rank (of 15) |", "|---|---|---|---|---|"]
    for col, name, nd, low in (("accuracy", "Winners called", 1, False), ("brier", "Brier", 3, True),
                               ("logloss", "Log loss", 3, True), ("coverage80", "80% range coverage", 1, False),
                               ("bias", "Mean margin error (+ = toward D/I)", 1, None)):
        v = {"accuracy": s["calls"] / s["n"], "brier": s["brier"], "logloss": s["logloss"],
             "coverage80": s["coverage80"], "bias": s["bias"]}[col]
        fmt = lambda x, col=col, nd=nd: (f"{x:.{nd}%}" if col in ("accuracy", "coverage80")
                                          else f"{x:+.{nd}f}" if col == "bias" else f"{x:.{nd}f}")
        if col == "bias":  # the smallest miss ranks first
            rk = 1 + int((years["bias"].abs() < abs(v)).sum())
        elif col == "coverage80":  # closest to the 80% target ranks first
            rk = 1 + int(((years["coverage80"] - 0.8).abs() < abs(v - 0.8)).sum())
        else:
            rk = rank(col, v, low)
        L.append(f"| {name} | **{fmt(v)}** | {fmt(years[col].mean())} | {fmt(years[col].min())} to "
                 f"{fmt(years[col].max())} | {rk} |")
    L += ["", "Rank 1 is the best year: the smallest miss for the mean error, and the closest to 80% for coverage.", "",
          "## Polls, fundamentals and the blend", "",
          f"In the {s['n_polled']} polled races with a result, root-mean-square error of the margin:", "",
          "| Estimate | RMSE (points) |", "|---|---|",
          f"| Poll average | {s['rmse_polled_polls']:.1f} |",
          f"| Fundamentals only | {s['rmse_polled_fundamentals']:.1f} |",
          f"| Blend (the forecast) | **{s['rmse_polled_blend']:.1f}** |", "",
          f"The poll averages themselves missed by {s['bias_polled_polls']:+.1f} points on average "
          "(+ = Democrats and independents did better than their polls). In 2026 the polls alone beat the "
          "blend: the fundamentals leaned further toward Republicans than the result did, and the blend "
          "inherited part of that lean. One year is not enough to change the weighting, which the backtest "
          "chose over 14 elections.", "",
          "## Race by race", "",
          "Sorted by the forecast margin. Error is result minus forecast (+ = toward the Democrat or "
          "independent). ✓ means the favourite won.", "",
          "| State | Forecast | 80% range | Win prob. (D/I) | Result | Error | In range | Favourite won |",
          "|---|---|---|---|---|---|---|---|"]
    for _, r in d.sort_values("margin").iterrows():
        rng = f"{label(r['lo80'], r['nr_party'])} to {label(r['hi80'], r['nr_party'])}"
        win = r["cand_nr"] if r["winner"] == "nr" else r["cand_r"]
        if r["status"] == "reported":
            res = f"{label(r['actual'], r['nr_party'])} ({win.split()[-1]})"
            e = f"{r['actual'] - r['margin']:+.1f}"
            inr = "yes" if r["lo80"] <= r["actual"] <= r["hi80"] else "**no**"
        else:
            res, e, inr = f"{win.split()[-1]} wins (assumed)", "–", "–"
        fw = "✓" if (r["p_nr"] >= 0.5) == (r["winner"] == "nr") else "**✗ upset**"
        L.append(f"| {r['state']} | {label(r['margin'], r['nr_party'])} | {rng} | {r['p_nr']:.0%} | {res} | {e} | {inr} | {fw} |")
    L += ["", f"Results source: {source}. Regenerate with `python -W ignore -m scripts.results_2026`.", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-parse the results from a saved Wikipedia page")
    ap.add_argument("--page", type=Path, default=RAW / "wikipedia" / "2026_senate.html")
    args = ap.parse_args()
    res = refresh(args.page) if args.refresh else pd.read_csv(RESULTS)
    if (res["status"] == "missing").any():
        raise SystemExit(f"no result for: {', '.join(res.loc[res['status'] == 'missing', 'race_id'])}")
    fc, senate = forecast()
    d = fc.merge(res[["race_id", "winner", "margin_2p", "status", "note", "pct_nr", "pct_r", "source"]], on="race_id")
    d = d.rename(columns={"margin_2p": "actual"})
    source = res["source"].iloc[0]
    rev = re.search(r"revision (\d+)", source).group(1)
    edited = re.search(r"last edited (.+)\)", source).group(1)
    s = score(d, senate)
    years = backtest_years()
    REPORT.write_text(report(d, s, years, source))

    races = []
    for _, r in d.iterrows():
        rep = r["status"] == "reported"
        races.append({
            "race_id": r["race_id"], "winner": r["winner"], "status": r["status"],
            "margin": round(float(r["actual"]), 2) if rep else None,
            "pct_nr": r["pct_nr"] if rep else None, "pct_r": r["pct_r"] if rep else None,
            "favorite_won": bool((r["p_nr"] >= 0.5) == (r["winner"] == "nr")),
            "error": round(float(r["actual"] - r["margin"]), 2) if rep else None,
            "in80": bool(r["lo80"] <= r["actual"] <= r["hi80"]) if rep else None,
            "note": r["note"] if isinstance(r["note"], str) else "",
        })
    out = {"as_of": pd.Timestamp(edited).strftime("%d %b %Y"), "source": f"Wikipedia, 2026 United States Senate elections (revision {rev})",
           "source_url": PAGE_URL.format(rev=rev),
           "notes": [f"{r['state']}: {r['note']}." for _, r in d[d["status"] == "assumed"].iterrows()],
           "seats": {"nr": s["nr_seats"], "r": s["r_seats"]},
           "score": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()},
           "races": races}
    GUI_OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {REPORT.relative_to(ROOT)} and {GUI_OUT.relative_to(ROOT)}")
    print(json.dumps(out["score"], indent=1))


if __name__ == "__main__":
    main()
