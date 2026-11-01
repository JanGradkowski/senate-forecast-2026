import numpy as np
import pandas as pd
import pytest

from senate_forecast.data import races2026, results
from senate_forecast.forecast import errors, model
from senate_forecast.simulate import sim

POLL_CFG = {"cutoff_days": 5, "tau_days": 14, "default_n": 600, "partisan_weight": 0.5, "house_ridge": 1.0}


def test_poll_average_corrects_a_race_flooded_by_one_biased_pollster():
    # House effects are only identified relative to other pollsters, so the test checks the
    # gap between races: pollster H (+6 too D-friendly) floods race A and polls B once.
    truth = {"A": 2.0, "B": -4.0, "C": 10.0}
    plan = [("A", "H")] * 5 + [("B", "H")] + [(r, p) for r in truth for p in ("P1", "P2")]
    rows = []
    for race, pollster in plan:
        m = truth[race] + (6.0 if pollster == "H" else 0.0)
        rows.append({"race_id": race, "pollster": pollster, "pct_nr": 50 + m / 2, "pct_r": 50 - m / 2,
                     "end_date": pd.Timestamp("2026-10-25"), "election_date": pd.Timestamp("2026-11-03"),
                     "n": 600, "partisan": np.nan})
    df = pd.DataFrame(rows)
    avg = model.poll_average(df, POLL_CFG).set_index("race_id")["poll_avg"]
    naive = (100 * (df.pct_nr - df.pct_r) / 100).groupby(df.race_id).mean()
    true_gap = truth["A"] - truth["C"]
    assert abs((avg["A"] - avg["C"]) - true_gap) < abs((naive["A"] - naive["C"]) - true_gap) / 3


def test_blend_leans_on_polls_when_there_are_many():
    df = pd.DataFrame({"poll_avg": [5.0, 5.0], "n_eff": [20.0, 0.5], "w_sum": [5.0, 0.5]})
    out = model.blend(df, np.array([-5.0, -5.0]), np.array([8.0, 8.0]), model.PollError(4.0, 50.0))
    assert out["mu"].iloc[0] > out["mu"].iloc[1] > -5


def test_anchoring_hits_target_probabilities():
    fc = pd.DataFrame({"race_id": ["A", "B"], "mu": [3.0, -8.0], "s_post": [5.0, 5.0],
                       "region": ["South", "West"], "runoff_rule": ["plurality"] * 2, "nr_party": ["D"] * 2})
    em = errors.ErrorModel(2.5, 1.0, 1.0, 5)
    cfg = {"n_draws": 40000, "seed": 1, "ga_third_party_mean": 0.02, "ga_runoff_sd": 3.0,
           "ind_caucus_d": 0.5, "holdover_d": 34}
    s = sim.simulate(fc, em, cfg, {})
    target = np.array([0.30, 0.65])
    got = s.outcomes(s.anchored(target))["nr_wins"].mean(axis=0)
    assert got == pytest.approx(target, abs=0.01)


@pytest.mark.parametrize("name,last", [
    ("CORTEZ MASTO, CATHERINE", "MASTO"),   # MEDSL 2022 "LAST, FIRST"
    ("ANGUS S. KING, JR.", "KING"),         # suffix after a comma
    ("Ben Ray Luján", "LUJAN"),             # accents
    ("CINDY HYDE-SMITH", "HYDESMITH"),
])
def test_last_name(name, last):
    assert results.last_name(name) == last


def test_reversed_names_still_match():
    assert results.same_person("WYDEN", "WYDEN RON") and not results.same_person("WYDEN", "RON JOHNSON")


def test_race_table_flags_are_real_booleans():
    r = races2026.races().set_index("race_id")
    assert r["trade"].dtype == bool or set(r["trade"]) <= {True, False}
    assert not r.loc["MT", "trade"] and r.loc["ME", "rcv"] and not r.loc["MI", "rcv"]
    assert len(r) == 35
