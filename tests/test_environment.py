"""Smoke test: every library the pipeline depends on imports and works."""

import importlib

import pytest

CORE = [
    "numpy", "pandas", "pyarrow", "httpx", "dotenv", "yaml", "tqdm",
    "scipy", "sklearn", "statsmodels", "lightgbm", "cvxpy", "matplotlib",
]


@pytest.mark.parametrize("name", CORE)
def test_core_imports(name):
    importlib.import_module(name)


def test_package_imports():
    import senate_forecast  # noqa: F401


def test_cvxpy_solves_a_tiny_kelly_problem():
    # One binary contract priced at 0.40 that we think wins 60% of the time.
    # Full Kelly fraction for a binary contract is (p - price) / (1 - price) = 1/3.
    import cvxpy as cp
    import numpy as np

    p, price = 0.6, 0.4
    f = cp.Variable(nonneg=True)
    wealth_if_win = 1 + f * (1 - price) / price
    wealth_if_lose = 1 - f
    problem = cp.Problem(
        cp.Maximize(p * cp.log(wealth_if_win) + (1 - p) * cp.log(wealth_if_lose)),
        [f <= 1],
    )
    problem.solve()
    assert np.isclose(f.value, 1 / 3, atol=1e-3)
