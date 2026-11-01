"""The hand-checked 2026 race table, the national inputs, and the Wikipedia ratings table."""

import re

import numpy as np
import pandas as pd
import yaml

from senate_forecast.data.polls import STATE_PO
from senate_forecast.paths import EXTERNAL, RAW

# Probability that the side a rating favours wins. Rough historical hit rates for Cook-style
# categories; converted to logits and averaged across raters to get the consensus.
RATING_P = {"Tossup": 0.50, "Tilt": 0.60, "Lean": 0.75, "Likely": 0.90, "Safe": 0.985, "Solid": 0.985}


def races() -> pd.DataFrame:
    r = pd.read_csv(EXTERNAL / "races_2026.csv", keep_default_na=False)
    for c in ["special", "appointed_incumbent", "rcv", "trade"]:
        r[c] = r[c].astype(str).str.lower().map({"true": True, "false": False})
        if r[c].isna().any():
            raise ValueError(f"races_2026.csv: column {c} must be True/False")
    return r


def national() -> dict:
    return yaml.safe_load((EXTERNAL / "national_2026.yaml").read_text())


def _rating_to_p_nr(text: str) -> float:
    """'Lean D (flip)' -> P(non-R wins). Independents (Osborn) are rated on the D/I side."""
    m = re.match(r"(Tossup|Tilt|Lean|Likely|Safe|Solid)\s*([DRI])?", str(text).strip())
    if not m:
        return np.nan
    p = RATING_P[m.group(1)]
    return 0.5 if m.group(1) == "Tossup" else (p if m.group(2) in ("D", "I") else 1 - p)


def ratings_table(path, special_suffix: bool) -> pd.DataFrame:
    """Long table of a Wikipedia Senate ratings table: race_id, rater, rating, p_nr.

    With `special_suffix`, "Georgia (special)" becomes GA-S (the history convention); 2026 has
    one race per state, so its race_id is the bare state code.
    """
    tabs = pd.read_html(path)
    t = next(t for t in tabs if "Cook" in " ".join(map(str, t.columns)) and len(t) >= 30)
    t.columns = [c[1] if isinstance(c, tuple) else c for c in t.columns]
    state_col = t.columns[0]
    raters = [c for c in t.columns if re.search(r"\b(19|20)\d\d\b", str(c)) and "Last" not in str(c)]
    name = t[state_col].astype(str)
    special = name.str.contains(r"\(special\)")
    state = name.str.replace(r"\s*\(special\)", "", regex=True)
    t = t.assign(race_id=state.map(STATE_PO) + np.where(special & special_suffix, "-S", ""))
    t = t[state.isin(STATE_PO)]
    long = t.melt(id_vars="race_id", value_vars=raters, var_name="rater", value_name="rating")
    long["rater"] = long["rater"].str.split().str[0]
    long["p_nr"] = long["rating"].map(_rating_to_p_nr)
    return long


def ratings() -> pd.DataFrame:
    """2026 ratings (11 raters)."""
    return ratings_table(RAW / "wikipedia/2026_senate.html", special_suffix=False)


def consensus_from(long: pd.DataFrame) -> pd.Series:
    """Mean of rater probabilities in logit space, per race."""
    r = long.dropna(subset=["p_nr"])
    lg = np.log(r["p_nr"] / (1 - r["p_nr"]))
    m = lg.groupby(r["race_id"]).mean()
    return (1 / (1 + np.exp(-m))).rename("p_consensus")


def consensus() -> pd.Series:
    return consensus_from(ratings())
