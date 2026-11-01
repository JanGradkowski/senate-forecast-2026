"""Senate and generic-ballot polls in one schema: one row per poll, non-R vs R candidate shares.

Columns: cycle, state_po, special, pollster, end_date, election_date, n, partisan, pct_nr, pct_r.
"""

import numpy as np
import pandas as pd

from senate_forecast.paths import RAW

ELECTION_DATES = {2024: "2024-11-05", 2026: "2026-11-03"}
STATE_PO = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA",
    "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
COLUMNS = ["cycle", "state_po", "special", "pollster", "end_date", "election_date", "n",
           "partisan", "pct_nr", "pct_r", "name_nr"]


def _orient(df: pd.DataFrame) -> pd.DataFrame:
    """Put the Republican in pct_r and the non-Republican in pct_nr; drop R-vs-R and D-vs-D polls."""
    r1, r2 = df["cand1_party"] == "REP", df["cand2_party"] == "REP"
    keep = r1 ^ r2
    df = df[keep].copy()
    flip = (df["cand1_party"] == "REP").to_numpy()
    df["pct_nr"] = np.where(flip, df["cand2_pct"], df["cand1_pct"])
    df["pct_r"] = np.where(flip, df["cand1_pct"], df["cand2_pct"])
    if "cand1_name" in df:
        df["name_nr"] = np.where(flip, df["cand2_name"], df["cand1_name"])
    return df


def senate_polls_538() -> pd.DataFrame:
    """538 raw_polls: first-round Senate general polls from the final 21 days, 1998-2022."""
    rp = pd.read_csv(RAW / "538/raw_polls.csv", low_memory=False)
    code = rp["race"].str.split("_").str[1]
    rp = rp[code.isin(["Sen-G", "Sen-GS"]) & (rp["cycle"] % 2 == 0)].copy()
    rp["special"] = code[rp.index] == "Sen-GS"
    rp = _orient(rp)
    rp = rp.rename(columns={"location": "state_po", "samplesize": "n"})
    rp["end_date"] = _date(rp["polldate"])
    rp["election_date"] = _date(rp["electiondate"])
    return rp[COLUMNS]


def _date(s: pd.Series) -> pd.Series:
    """raw_polls mixes ISO dates and m/d/yy."""
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    return iso.fillna(pd.to_datetime(s, format="%m/%d/%y", errors="coerce"))


def _answers_538(path, cycle: int) -> pd.DataFrame:
    """538 live-format file (one row per candidate answer) to one row per poll."""
    d = pd.read_csv(path, low_memory=False)
    d = d[(d["cycle"] == cycle) & (d["stage"] == "general")]
    d = d[~d["hypothetical"].astype(str).str.lower().eq("true")]
    if "ranked_choice_reallocated" in d:
        d = d[~d["ranked_choice_reallocated"].astype(str).str.lower().eq("true")]
    return d


def senate_polls_2024() -> pd.DataFrame:
    d = _answers_538(RAW / "538/senate_polls_2024.csv", 2024)
    d["is_r"] = d["party"] == "REP"
    rows = []
    for qid, g in d.groupby("question_id"):
        r, nr = g[g["is_r"]], g[~g["is_r"]]
        if r.empty or nr.empty:
            continue
        f = g.iloc[0]
        rows.append({
            "poll_id": f["poll_id"], "population": str(f["population"]).lower(),
            "cycle": 2024, "state_po": STATE_PO.get(f["state"]),
            "special": f["seat_name"] != "Class I",  # Class I was the regular class in 2024
            "pollster": f["pollster"], "end_date": pd.to_datetime(f["end_date"]),
            "election_date": pd.Timestamp(ELECTION_DATES[2024]), "n": f["sample_size"],
            "partisan": f["partisan"], "pct_nr": nr["pct"].max(), "pct_r": r["pct"].max(),
            "name_nr": nr.loc[nr["pct"].idxmax(), "candidate_name"],
        })
    df = pd.DataFrame(rows).dropna(subset=["state_po"])
    # one question per poll: prefer likely voters, then registered voters
    rank = df["population"].map({"lv": 0, "rv": 1}).fillna(2)
    df = df.assign(_rank=rank).sort_values("_rank").drop_duplicates(["poll_id", "special"])
    return df[COLUMNS]


def senate_polls_2026(aligned_ind: set[str]) -> pd.DataFrame:
    """electoral-vote.com 2026 polls. States in `aligned_ind` use the Ind column as the non-R."""
    e = pd.read_csv(RAW / "evp/senate_polls.csv")
    e = e.loc[:, ~e.columns.str.startswith("Unnamed")]
    e = e[~e["Pollster"].str.startswith("Election 20")]  # previous-result placeholders
    e = e.drop_duplicates(["State", "Pollster", "Day", "Dem", "GOP", "Ind"])
    e["state_po"] = e["State"].map(STATE_PO)
    e["pollster"] = e["Pollster"].str.replace(r"-\d+$", "", regex=True)
    end_doy = e["Day"] + (e["Len"] - 1) / 2
    e["end_date"] = pd.Timestamp("2026-01-01") + pd.to_timedelta(end_doy.round() - 1, unit="D")
    ind = e["state_po"].isin(aligned_ind)
    e["pct_nr"] = np.where(ind, e["Ind"], e["Dem"])
    e["pct_r"] = e["GOP"]
    e = e.dropna(subset=["pct_nr", "pct_r"])
    e = e.assign(cycle=2026, special=e["state_po"].isin(["OH", "FL"]), n=np.nan, partisan=np.nan,
                 election_date=pd.Timestamp(ELECTION_DATES[2026]), name_nr=np.nan)
    return e[COLUMNS]


def generic_ballot(cutoff_days: int = 5) -> pd.Series:
    """Average generic-ballot D margin per cycle from polls in the final 21 days ending by T-5."""
    rp = pd.read_csv(RAW / "538/raw_polls.csv", low_memory=False)
    g = rp[rp["type_simple"] == "House-G-US"].copy()
    g = _orient(g)
    g["end_date"] = _date(g["polldate"])
    g["election_date"] = _date(g["electiondate"])
    g24 = pd.read_csv(RAW / "538/generic_ballot_polls_2024.csv", low_memory=False)
    g24 = g24[g24["cycle"] == 2024]
    g24 = pd.DataFrame({"cycle": 2024, "end_date": pd.to_datetime(g24["end_date"]),
                        "election_date": pd.Timestamp(ELECTION_DATES[2024]),
                        "pct_nr": g24["dem"], "pct_r": g24["rep"]})
    g24 = g24[g24["end_date"] >= g24["election_date"] - pd.Timedelta(days=21)]
    g = pd.concat([g[["cycle", "end_date", "election_date", "pct_nr", "pct_r"]], g24])
    g = g[g["end_date"] <= g["election_date"] - pd.Timedelta(days=cutoff_days)]
    return (g["pct_nr"] - g["pct_r"]).groupby(g["cycle"]).mean().rename("generic_ballot")
