"""Export the 2026 Senate forecast for the map GUI (gui/): writes gui/data/senate.json.

Usage: python -W ignore -m scripts.export_gui [--market]   (after scripts.forecast)
Everything comes from the project's outputs: race-level projections from
artifacts/forecast_2026.csv, the seat distribution from artifacts/sims_2026.npz and seats not up
from configs/forecast.yaml. Margins are two-party, in percentage points: non-Republican share
minus Republican share. --market adds each race's prediction-market probability from the latest
fetched price sheet (needs the market tools); without it the field is null and the GUI hides it.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
import yaml

from senate_forecast.paths import ARTIFACTS, CONFIGS, ROOT

OUT = ROOT / "gui" / "data" / "senate.json"


def _num(x, nd=3):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def market_probs(fc: pd.DataFrame) -> pd.Series:
    try:
        from senate_forecast.live import inputs  # market tools: optional
    except ImportError:
        raise SystemExit("--market needs the market tools (senate_forecast.live), which are not part of this release")
    _, acfg, _ = inputs.configs()
    return inputs.beliefs(fc, inputs.latest_prices(), acfg)["p_mkt"]


def build(market: bool = False) -> dict:
    fcfg = yaml.safe_load((CONFIGS / "forecast.yaml").read_text())
    fc = pd.read_csv(ARTIFACTS / "forecast_2026.csv", keep_default_na=False, na_values=[""])
    p_mkt = market_probs(fc) if market else pd.Series(dtype=float)
    sims = np.load(ARTIFACTS / "sims_2026.npz")
    seats = pd.Series(sims["d_seats"]).value_counts(normalize=True).sort_index()
    sim = fcfg["simulation"]
    races = []
    for r in fc.itertuples():
        races.append({
            "race_id": r.race_id, "state": r.state, "postal": r.state_po, "special": bool(r.special),
            "nr": {"name": r.cand_nr, "party": r.nr_party}, "r": {"name": r.cand_r, "party": "R"},
            "incumbent": {1: "nr", -1: "r"}.get(int(r.incumbent), None),
            "margin": _num(r.mu), "lo80": _num(r.lo80), "hi80": _num(r.hi80),  # 3 decimals: the GUI rounds once
            "p_nr": _num(r.p_nr), "p_runoff": _num(r.p_runoff), "p_consensus": _num(r.p_consensus),
            "p_market": _num(p_mkt.get(r.race_id)),
            "polls": {"n": int(r.n_polls) if pd.notna(r.n_polls) else 0, "avg": _num(r.poll_avg)},
            "rcv": bool(r.rcv), "runoff": r.runoff_rule == "majority", "notes": r.notes if isinstance(r.notes, str) else "",
        })
    mtime = pd.Timestamp(os.path.getmtime(ARTIFACTS / "forecast_2026.csv"), unit="s", tz="UTC").tz_convert("Europe/Brussels")
    return {
        "chamber": "senate", "as_of": f"{mtime:%d %b %Y}", "majority": 51,
        "not_up": {"nr": sim["holdover_d"], "r": sim["holdover_r"]},
        "p_control_nr": _num((sims["d_seats"] >= 51).mean()), "median_nr_seats": int(np.median(sims["d_seats"])),
        "seat_distribution": [{"seats": int(k), "p": _num(v, 4)} for k, v in seats.items()],
        "n_draws": len(sims["d_seats"]), "races": races,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", action="store_true", help="add prediction-market probabilities (market tools needed)")
    data = build(ap.parse_args().market)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(data['races'])} races, P(D control) {data['p_control_nr']}, "
          f"median {data['median_nr_seats']} seats, as of {data['as_of']}")
