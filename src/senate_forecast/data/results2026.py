"""Actual 2026 Senate results, parsed from Wikipedia's "2026 United States Senate elections" page.

Each race section on that page has an election infobox with the nominees, their parties, popular votes and
percentages. The model's two candidates in each race (data/external/races_2026.csv) are matched by last
name, and the two-party margin is computed from their votes on the same scale the model forecast:
non-Republican share minus Republican share, in points, other candidates excluded.

A race the page does not settle yet (Alaska's ranked-choice tabulation, for instance) can be filled
from ASSUMED. That gives a winner but no margin, and it is labelled as an assumption everywhere it is
shown.
"""

from __future__ import annotations

import re

import pandas as pd
from lxml import html as lhtml

from senate_forecast.data.results import last_name

# Races the page did not settle when the results were taken, with the outcome assumed for scoring.
ASSUMED = {
    "AK": {"winner": "nr", "note": "Ranked-choice tabulation pending; a Democratic win (Peltola) is assumed"},
}


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.text_content()).strip()


def _num(s: str) -> float | None:
    s = s.replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def infobox(doc, section_id: str) -> dict | None:
    """Nominees, parties, votes and percentages from the infobox that follows a section heading."""
    heads = doc.xpath(f'//*[@id="{section_id}"]')
    if not heads:
        return None
    boxes = heads[0].xpath("following::table[contains(concat(' ', @class, ' '), ' infobox ')][1]")
    if not boxes:
        return None
    rows = {}
    for tr in boxes[0].xpath(".//tr"):
        cells = [_text(c) for c in tr.xpath("./th|./td")]
        if cells and cells[0] in ("Nominee", "Party", "Popular vote", "Percentage") and cells[0] not in rows:
            rows[cells[0]] = cells[1:]
    if "Nominee" not in rows or "Popular vote" not in rows:
        return None
    n = len([x for x in rows["Nominee"] if x])
    return {k: v[:n] for k, v in rows.items()}


def parse_wikipedia(page_html: str, races: pd.DataFrame, source: str) -> pd.DataFrame:
    """One row per 2026 race: the model's two candidates' votes, the two-party margin and the winner."""
    doc = lhtml.fromstring(page_html)
    out = []
    for r in races.itertuples():
        sid = r.state.replace(" ", "_") + ("_(special)" if str(r.special) == "True" else "")
        box = infobox(doc, sid)
        row = {"race_id": r.race_id, "state": r.state, "special": r.special, "cand_nr": r.cand_nr,
               "party_nr": r.nr_party, "cand_r": r.cand_r, "votes_nr": None, "pct_nr": None, "votes_r": None,
               "pct_r": None, "winner": None, "margin_2p": None, "status": None, "note": "", "source": source}
        if box:
            names = [last_name(x) for x in box["Nominee"]]
            for side, cand in (("nr", r.cand_nr), ("r", r.cand_r)):
                if last_name(cand) in names:
                    i = names.index(last_name(cand))
                    row[f"votes_{side}"] = _num(box["Popular vote"][i])
                    row[f"pct_{side}"] = _num(box.get("Percentage", [""] * len(names))[i])
        vn, vr = row["votes_nr"], row["votes_r"]
        if vn and vr:
            row["margin_2p"] = round(100 * (vn - vr) / (vn + vr), 3)
            row["winner"] = "nr" if vn > vr else "r"
            row["status"] = "reported"
        elif r.race_id in ASSUMED:
            row.update(winner=ASSUMED[r.race_id]["winner"], status="assumed", note=ASSUMED[r.race_id]["note"])
        else:
            row.update(status="missing", note="no result on the page")
        out.append(row)
    return pd.DataFrame(out)
