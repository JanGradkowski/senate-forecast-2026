"""Joint calibration of the tuned Model 1 (build item #10 of arena/chase_verdict.md).

Per held-out year (leave-one-year-out, 1998-2024), among races forecast within 15 points:
  - seat-count PIT: where the observed number of non-R wins falls in the predicted distribution;
  - upset-count PIT: the same for the number of favourites who lost.
A model whose shared (national and regional) errors are right gives PITs spread evenly over 0-1.
Gate: at most 3 of 14 years in the outer 10% (below 0.05 or above 0.95) for each.
Writes reports/joint_calibration.md. Usage: python -W ignore -m scripts.joint_check
"""

import numpy as np
import yaml

from scripts.evaluate import load
from senate_forecast.evaluate import loyo
from senate_forecast.paths import CONFIGS, REPORTS

if __name__ == "__main__":
    cfg = yaml.safe_load((CONFIGS / "forecast.yaml").read_text())
    hist, _ = load(cfg)
    years = sorted(hist["cycle"].unique())
    pred = loyo.out_of_sample(hist, cfg["features"], [([c for c in years if c != y], y) for y in years])
    prob = loyo.probabilities(pred, cfg["errors"], cfg["simulation"]["seed"])
    t = prob.groupby("cycle")[["count_pit", "upset_pit", "count_nll"]].first()
    outer = {c: int(((t[c] < 0.05) | (t[c] > 0.95)).sum()) for c in ("count_pit", "upset_pit")}
    ok = all(v <= 3 for v in outer.values())
    lines = ["# Joint calibration (tuned Model 1, leave-one-year-out)", "",
             f"**{'PASS' if ok else 'FAIL'}**: years in the outer 10% — seat count {outer['count_pit']} of {len(t)}, "
             f"upsets {outer['upset_pit']} of {len(t)} (gate: at most 3 each; about 1.4 expected by chance).", "",
             f"Mean PIT: seat count {t['count_pit'].mean():.2f}, upsets {t['upset_pit'].mean():.2f} (0.50 if unbiased). "
             f"Share of years in the middle half: {np.mean(t['count_pit'].between(0.25, 0.75)):.0%} "
             f"(50% if the spread is right; more = too wide, less = too narrow).", "",
             t.round(3).to_markdown()]
    (REPORTS / "joint_calibration.md").write_text("\n".join(lines))
    print("\n".join(lines))
