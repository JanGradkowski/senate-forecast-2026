"""One feature function for history and 2026, so training and live inputs are the same variables."""

import numpy as np
import pandas as pd

from senate_forecast.data import polls, races2026, results

REGION = {
    "Northeast": "ME NH VT MA RI CT NY NJ PA",
    "Midwest": "OH MI IN IL WI MN IA MO ND SD NE KS",
    "South": "DE MD DC VA WV NC SC GA FL KY TN AL MS AR LA OK TX",
    "West": "MT ID WY CO NM AZ UT NV CA OR WA AK HI",
}
REGION_OF = {st: reg for reg, sts in REGION.items() for st in sts.split()}

# Party of the president during each cycle: +1 D, -1 R
PRES_PARTY = {1998: 1, 2000: 1, 2002: -1, 2004: -1, 2006: -1, 2008: -1, 2010: 1, 2012: 1,
              2014: 1, 2016: 1, 2018: -1, 2020: -1, 2022: 1, 2024: 1, 2026: -1}


def _national(races: pd.DataFrame, generic: pd.Series) -> pd.DataFrame:
    races = races.copy()
    races["generic_ballot"] = races["cycle"].map(generic)
    midterm = races["cycle"] % 4 == 2
    # Midterms hurt the president's party: with a D president this lowers the non-R margin.
    races["midterm_penalty"] = midterm.astype(int) * races["cycle"].map(PRES_PARTY)
    races["region"] = races["state_po"].map(REGION_OF)
    return races


def _with_lean(races: pd.DataFrame) -> pd.DataFrame:
    pm = results.president_margins()
    leans = pd.concat([results.pres_lean(c, pm).assign(cycle=c) for c in races["cycle"].unique()])
    return races.merge(leans, on=["cycle", "state_po"], how="left")


def history(cycles: list[int]) -> pd.DataFrame:
    """Contested two-way Senate races with outcomes, one row per race."""
    r = results.senate_races()
    r = r[r["cycle"].isin(cycles) & r["contested"]].copy()
    r["race_id"] = r["state_po"] + r["special"].map({True: "-S", False: ""})
    r = _with_lean(r)
    return _national(r, polls.generic_ballot())


def live_2026() -> pd.DataFrame:
    """The 35 races of 2026 with the same feature columns (no outcome)."""
    r = races2026.races().rename(columns={"race_id": "state_po"})
    r["race_id"] = r["state_po"]
    r["cycle"] = 2026
    r = _with_lean(r)
    nat = races2026.national()
    return _national(r, pd.Series({2026: nat["generic_ballot"]}))


def match_candidates(p: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """Drop polls whose non-R candidate is not the race's main non-R candidate.

    538's archive sometimes records a race's poll as the third-place Democrat vs the Republican
    (Maine 2012/2018, where independent King was the real opponent). Polls without names pass.
    """
    m = p.merge(races[["cycle", "race_id", "cand_nr"]], on=["cycle", "race_id"], how="left")
    named = m["name_nr"].notna() & m["cand_nr"].notna()
    same = np.array([results.same_person(results.last_name(a), b) for a, b in zip(m["name_nr"], m["cand_nr"])])
    return p[~named.to_numpy() | same]


def poll_table(cycles: list[int], aligned_ind_2026: set[str]) -> pd.DataFrame:
    """All polls for the given cycles (2026 included if requested) with a race_id."""
    parts = [polls.senate_polls_538(), polls.senate_polls_2024()]
    if 2026 in cycles:
        parts.append(polls.senate_polls_2026(aligned_ind_2026))
    p = pd.concat(parts, ignore_index=True)
    p = p[p["cycle"].isin(cycles)].copy()
    p["race_id"] = p["state_po"] + p["special"].map({True: "-S", False: ""})
    if 2026 in cycles:  # 2026 has one race per state, so drop the special suffix there
        p.loc[p["cycle"] == 2026, "race_id"] = p.loc[p["cycle"] == 2026, "state_po"]
    return p
