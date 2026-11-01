"""Senate and presidential results from MIT Election Lab, reduced to one row per race."""

import re
import unicodedata

import numpy as np
import pandas as pd

from senate_forecast.paths import RAW

NOT_A_CANDIDATE = {"", "OTHER", "SCATTERING", "WRITEIN", "BLANK VOTE", "OVER VOTE", "UNDER VOTE"}
SUFFIXES = {"JR", "SR", "II", "III", "IV"}


def name_tokens(name: str) -> list[str]:
    """Upper-case ASCII words of a name, without suffixes (Luján -> LUJAN)."""
    if not isinstance(name, str):
        return []
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return [p for p in re.sub(r"[^A-Z ]", "", ascii_name.upper()).split() if p not in SUFFIXES]


def last_name(name: str) -> str:
    """Last name. MEDSL 2018/2022 sometimes writes "LAST, FIRST"; "FIRST LAST, JR." also has a
    comma; in both, the last name is the final word before the comma."""
    if not isinstance(name, str):
        return ""
    parts = name_tokens(name.split(",")[0])
    return parts[-1] if parts else ""


def same_person(known_last: str, name: str) -> bool:
    """True if `name` contains `known_last` as a word: also covers "WYDEN RON" (2022)."""
    return bool(known_last) and known_last in name_tokens(name)


def _senate_rows() -> pd.DataFrame:
    s = pd.read_csv(RAW / "medsl/senate.csv")
    s["stage"] = s["stage"].str.lower()
    s["candidate"] = s["candidate"].fillna("").str.upper().str.strip()
    s = s[~s["writein"] & ~s["candidate"].isin(NOT_A_CANDIDATE)]
    # 2021 rows are the January Georgia runoffs that belong to the 2020 cycle
    s["cycle"] = s["year"] - (s["year"] % 2)
    return s


def _by_candidate(rows: pd.DataFrame) -> pd.DataFrame:
    """Sum fusion lines per candidate; a candidate is R (or D) if any of their lines is."""
    g = rows.groupby("candidate").agg(
        votes=("candidatevotes", "sum"),
        is_r=("party_simplified", lambda p: (p == "REPUBLICAN").any()),
        is_d=("party_simplified", lambda p: (p == "DEMOCRAT").any()),
    )
    return g.sort_values("votes", ascending=False)


def senate_races() -> pd.DataFrame:
    """One row per first-round general election: strongest Republican vs strongest non-Republican.

    `nr` is the strongest non-Republican (a Democrat, or an independent such as King, Sanders,
    Osborn). Races whose top two are not one R and one non-R (CA top-two, AK 2022) are flagged
    `two_way=False` and excluded from training.
    """
    s = _senate_rows()
    out = []
    for (cycle, st, special), g in s[s["stage"] == "gen"].groupby(["cycle", "state_po", "special"]):
        c = _by_candidate(g)
        total = g["totalvotes"].max()
        r, nr = c[c["is_r"]], c[~c["is_r"]]
        if r.empty or nr.empty:
            continue
        top2_r = c["is_r"].iloc[:2].sum()
        out.append({
            "cycle": cycle, "state_po": st, "special": bool(special),
            "cand_r": r.index[0], "votes_r": r["votes"].iloc[0],
            "cand_nr": nr.index[0], "votes_nr": nr["votes"].iloc[0],
            "nr_is_dem": bool(nr["is_d"].iloc[0]), "totalvotes": total,
            "two_way": top2_r == 1 and len(c) >= 2,
        })
    df = pd.DataFrame(out)
    df["margin_2p"] = 100 * (df["votes_nr"] - df["votes_r"]) / (df["votes_nr"] + df["votes_r"])
    df["share_r"] = df["votes_r"] / df["totalvotes"]
    df["share_nr"] = df["votes_nr"] / df["totalvotes"]
    df["contested"] = df["two_way"] & (df[["share_r", "share_nr"]].min(axis=1) >= 0.05)
    df["nr_won"] = df["margin_2p"] > 0
    df["incumbent"] = _incumbency(df, s)
    return df.sort_values(["cycle", "state_po", "special"]).reset_index(drop=True)


def _winners(s: pd.DataFrame) -> pd.DataFrame:
    """Winner of every Senate race (runoff winner where a runoff happened)."""
    rows = []
    for (cycle, st, special), g in s.groupby(["cycle", "state_po", "special"]):
        runoff = g["stage"].str.contains("runoff")  # labelled "runoff" or "gen runoff"
        c = _by_candidate(g[runoff] if runoff.any() else g[g["stage"] == "gen"])
        if not c.empty:
            rows.append({"cycle": cycle, "state_po": st, "winner": last_name(c.index[0])})
    return pd.DataFrame(rows)


def _incumbency(races: pd.DataFrame, s: pd.DataFrame) -> np.ndarray:
    """+1 if the non-R candidate is an incumbent, -1 if the R is, else 0.

    A candidate counts as incumbent if they won a Senate race in the same state in the previous
    six years. Appointed senators who never won are coded as open seats here; 2026 appointees
    get the plan's x0.5 treatment in the 2026 race table instead.
    """
    w = _winners(s)
    inc = []
    for row in races.itertuples():
        past = w[(w["state_po"] == row.state_po) & (w["cycle"] < row.cycle) & (w["cycle"] >= row.cycle - 6)]
        names = set(past["winner"])
        r_inc = any(same_person(n, row.cand_r) for n in names)
        nr_inc = any(same_person(n, row.cand_nr) for n in names)
        inc.append(1 if nr_inc and not r_inc else -1 if r_inc and not nr_inc else 0)
    return np.array(inc)


def president_margins() -> pd.DataFrame:
    """Two-party D margin by state and nationally for every presidential year."""
    p = pd.read_csv(RAW / "medsl/president.csv")
    p = p[p["party_simplified"].isin(["DEMOCRAT", "REPUBLICAN"])]
    v = p.pivot_table(index=["year", "state_po"], columns="party_simplified",
                      values="candidatevotes", aggfunc="sum").reset_index()
    v["margin"] = 100 * (v["DEMOCRAT"] - v["REPUBLICAN"]) / (v["DEMOCRAT"] + v["REPUBLICAN"])
    nat = v.groupby("year")[["DEMOCRAT", "REPUBLICAN"]].sum()
    nat["nat_margin"] = 100 * (nat["DEMOCRAT"] - nat["REPUBLICAN"]) / (nat["DEMOCRAT"] + nat["REPUBLICAN"])
    return v.merge(nat["nat_margin"].reset_index(), on="year")[["year", "state_po", "margin", "nat_margin"]]


def pres_lean(cycle: int, pm: pd.DataFrame) -> pd.DataFrame:
    """State lean for a Senate cycle from the two presidential elections strictly before it."""
    years = sorted(y for y in pm["year"].unique() if y < cycle)[-2:]
    prev, last = years
    a = pm[pm["year"] == last].set_index("state_po")
    b = pm[pm["year"] == prev].set_index("state_po")
    lean = 0.75 * (a["margin"] - a["nat_margin"]) + 0.25 * (b["margin"] - b["nat_margin"])
    return pd.DataFrame({"pres_lean": lean, "last_pres_nat": a["nat_margin"].iloc[0]}).reset_index()
