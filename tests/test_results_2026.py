"""2026 results: the Wikipedia parser, the committed results and the data the map's results view reads."""

import json

import pandas as pd
import pytest

from scripts.results_2026 import md_table
from senate_forecast.data.results2026 import ASSUMED, parse_wikipedia
from senate_forecast.paths import EXTERNAL, REPORTS, ROOT

PAGE = """<html><body>
<h3 id="Iowa">Iowa</h3>
<table class="infobox ib-election"><tr><th>Nominee</th><td>Josh Turek</td><td>Ashley Hinson</td></tr>
<tr><th>Party</th><td>Democratic</td><td>Republican</td></tr>
<tr><th>Popular vote</th><td>600,000</td><td>400,000</td></tr>
<tr><th>Percentage</th><td>58.0%</td><td>38.7%</td></tr></table>
<h3 id="Nebraska">Nebraska</h3>
<table class="infobox ib-election"><tr><th>Nominee</th><td>Pete Ricketts</td><td>Dan Osborn</td><td>Someone Else</td></tr>
<tr><th>Party</th><td>Republican</td><td>Independent</td><td>Libertarian</td></tr>
<tr><th>Popular vote</th><td>550,000</td><td>450,000</td><td>20,000</td></tr>
<tr><th>Percentage</th><td>53.9%</td><td>44.1%</td><td>2.0%</td></tr></table>
<h3 id="Alaska">Alaska</h3><p>Count pending.</p>
</body></html>"""


def test_parser_matches_candidates_and_computes_two_party_margins():
    races = pd.DataFrame([
        {"race_id": "IA", "state": "Iowa", "special": False, "cand_nr": "Josh Turek", "nr_party": "D", "cand_r": "Ashley Hinson"},
        {"race_id": "NE", "state": "Nebraska", "special": False, "cand_nr": "Dan Osborn", "nr_party": "I", "cand_r": "Pete Ricketts"},
        {"race_id": "AK", "state": "Alaska", "special": False, "cand_nr": "Mary Peltola", "nr_party": "D", "cand_r": "Dan S. Sullivan"},
    ])
    d = parse_wikipedia(PAGE, races, source="test").set_index("race_id")
    assert d.loc["IA", "margin_2p"] == pytest.approx(20.0)  # (600k - 400k) / 1m
    assert d.loc["IA", "winner"] == "nr"
    # columns follow the page, not the model: Osborn is second; the third candidate is left out
    assert d.loc["NE", "votes_nr"] == 450_000 and d.loc["NE", "votes_r"] == 550_000
    assert d.loc["NE", "margin_2p"] == pytest.approx(-10.0)
    assert d.loc["NE", "winner"] == "r"
    # no infobox numbers: the documented assumption, with no margin
    assert d.loc["AK", "status"] == "assumed" and d.loc["AK", "winner"] == ASSUMED["AK"]["winner"]
    assert pd.isna(d.loc["AK", "margin_2p"])


@pytest.fixture(scope="module")
def results():
    return pd.read_csv(EXTERNAL / "results_2026.csv")


def test_every_race_has_a_result(results):
    assert len(results) == 35 and results["race_id"].is_unique
    assert set(results["status"]) <= {"reported", "assumed"}
    rep = results[results["status"] == "reported"]
    assert rep["margin_2p"].notna().all()
    assert ((rep["margin_2p"] > 0) == (rep["winner"] == "nr")).all()
    recomputed = 100 * (rep["votes_nr"] - rep["votes_r"]) / (rep["votes_nr"] + rep["votes_r"])
    assert (recomputed - rep["margin_2p"]).abs().max() < 1e-3


def test_results_view_data_is_consistent(results):
    senate = json.loads((ROOT / "gui" / "data" / "senate.json").read_text())
    out = json.loads((ROOT / "gui" / "data" / "results.json").read_text())
    assert out["seats"]["nr"] + out["seats"]["r"] == 100
    assert out["seats"]["nr"] == senate["not_up"]["nr"] + int((results["winner"] == "nr").sum())
    p = {r["race_id"]: r["p_nr"] for r in senate["races"]}
    for r in out["races"]:
        assert r["favorite_won"] == ((p[r["race_id"]] >= 0.5) == (r["winner"] == "nr")), r["race_id"]
    assert out["score"]["calls"] == sum(r["favorite_won"] for r in out["races"])


def test_map_labels_match_the_unrounded_forecast():
    """The map rounds each margin once; it must agree with the forecast report to one decimal."""
    f = md_table((REPORTS / "forecast_2026.md").read_text(), "| race_id").set_index("race_id")
    senate = json.loads((ROOT / "gui" / "data" / "senate.json").read_text())
    for r in senate["races"]:
        assert f"{abs(r['margin']):.1f}" == f"{abs(float(f.loc[r['race_id'], 'mu'])):.1f}", r["race_id"]
