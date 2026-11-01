import re

import numpy as np
import pytest

from scripts import export_gui
from senate_forecast.paths import ARTIFACTS, REPORTS

pytestmark = pytest.mark.skipif(not (ARTIFACTS / "sims_2026.npz").exists(), reason="run scripts.forecast first")


@pytest.fixture(scope="module")
def data():
    return export_gui.build()


def test_every_2026_race_is_exported(data):
    assert len(data["races"]) == 35
    assert len({r["race_id"] for r in data["races"]}) == 35


def test_margin_sign_agrees_with_win_probability(data):
    for r in data["races"]:
        if abs(r["margin"]) > 0.5:  # near zero the t-tails can tip the probability either way
            assert (r["margin"] > 0) == (r["p_nr"] > 0.5), r["race_id"]
        assert r["lo80"] <= r["margin"] <= r["hi80"], r["race_id"]


def test_seat_distribution_is_a_distribution_and_matches_control(data):
    p = np.array([s["p"] for s in data["seat_distribution"]])
    assert p.sum() == pytest.approx(1, abs=1e-3)
    tail = sum(s["p"] for s in data["seat_distribution"] if s["seats"] >= data["majority"])
    assert tail == pytest.approx(data["p_control_nr"], abs=2e-3)


def test_headline_numbers_match_the_forecast_report(data):
    text = (REPORTS / "forecast_2026.md").read_text()
    m = re.search(r"Senate\) = \*\*([\d.]+)%\*\* .*median D\+I seats (\d+)", text)
    assert data["p_control_nr"] * 100 == pytest.approx(float(m.group(1)), abs=0.06)
    assert data["median_nr_seats"] == int(m.group(2))
