"""Correlated Monte Carlo of the whole 2026 map, with Georgia's runoff rule and Senate control."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from senate_forecast.forecast import errors


@dataclass
class MapSims:
    """Draws of first-round margins plus the extra random numbers that turn margins into
    outcomes. Keeping those fixed means outcomes can be recomputed for shifted margins with
    common random numbers (used to anchor races to a target probability)."""
    race_ids: list[str]
    margin: np.ndarray        # (draws, races) first-round non-R margin, points
    majority: np.ndarray      # (races,) bool, majority-or-runoff rule (Georgia)
    is_ind: np.ndarray        # (races,) bool, non-R candidate is an independent
    third: np.ndarray         # (draws,) third-party share for majority-rule races
    runoff_noise: np.ndarray  # (draws,) runoff margin minus first-round margin
    caucus_d: np.ndarray      # (draws, races) bool, a winning independent caucuses with D
    holdover_d: int

    def outcomes(self, margin: np.ndarray | None = None) -> dict:
        m = self.margin if margin is None else margin
        wins = m > 0
        runoff = np.zeros_like(wins)
        for i in np.flatnonzero(self.majority):
            lead_share = (1 - self.third) * (1 + np.abs(m[:, i]) / 100) / 2
            runoff[:, i] = lead_share < 0.5
            wins[:, i] = np.where(runoff[:, i], m[:, i] + self.runoff_noise > 0, m[:, i] > 0)
        d_seats = self.holdover_d + (wins & (~self.is_ind | self.caucus_d)).sum(axis=1)
        return {"nr_wins": wins, "runoff": runoff, "d_seats": d_seats, "d_control": d_seats >= 51}

    def anchored(self, p_target: np.ndarray) -> np.ndarray:
        """Margins shifted race by race so P(margin > 0) equals p_target (NaN = no shift)."""
        q = np.nanquantile(self.margin, np.clip(1 - np.nan_to_num(p_target, nan=0.5), 1e-4, 1 - 1e-4), axis=0)
        shift = -np.diagonal(q) if q.ndim == 2 else -q
        shift = np.where(np.isnan(p_target), 0.0, shift)
        return self.margin + shift

    def summary(self, fc: pd.DataFrame) -> pd.DataFrame:
        o = self.outcomes()
        lo, hi = np.quantile(self.margin, [0.1, 0.9], axis=0)
        return fc.assign(p_nr=o["nr_wins"].mean(axis=0), p_runoff=o["runoff"].mean(axis=0),
                         lo80=lo, hi80=hi)


def simulate(fc: pd.DataFrame, em: errors.ErrorModel, cfg: dict, extra_sd: dict,
             seed: int | None = None, n: int | None = None) -> MapSims:
    """fc: one row per race with mu, s_post, region, runoff_rule, nr_party, race_id."""
    rng = np.random.default_rng(cfg["seed"] if seed is None else seed)
    n = n or cfg["n_draws"]
    extra = fc["race_id"].map(extra_sd).fillna(1.0).to_numpy()
    e = errors.predictive_errors(fc["s_post"].to_numpy(), fc["region"].to_numpy(), em, n, rng, extra)
    m = cfg["ga_third_party_mean"]
    return MapSims(
        race_ids=list(fc["race_id"]),
        margin=fc["mu"].to_numpy() + e,
        majority=(fc["runoff_rule"] == "majority").to_numpy(),
        is_ind=(fc["nr_party"] == "I").to_numpy(),
        third=rng.beta(200 * m, 200 * (1 - m), n),
        runoff_noise=rng.normal(0, cfg["ga_runoff_sd"], n),
        caucus_d=rng.random((n, len(fc))) < cfg["ind_caucus_d"],
        holdover_d=cfg["holdover_d"],
    )
