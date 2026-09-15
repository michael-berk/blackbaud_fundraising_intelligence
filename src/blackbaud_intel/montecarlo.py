"""Monte Carlo campaign-forecast simulation (decision-science method #4).

The descriptive forecast is a point estimate: sum of ask_amount * win_probability.
That hides risk. Here each open opportunity is modelled as a Bernoulli trial that
either lands its full ask (prob = win_probability) or nothing. Simulating the whole
open pipeline many times yields a *distribution* of campaign totals, so leadership
can see the P10 / P50 / P90 range and the probability of clearing goal — not a
single misleading number.

Pure-Python core (``simulate``) so it is unit-testable without Spark; the notebook
wrapper pulls opportunities from ``opp_enriched`` and persists the percentiles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ForecastDistribution:
    """Percentile summary of simulated campaign totals."""

    committed: float
    p10: float
    p50: float
    p90: float
    mean: float
    probability_of_goal: float


def simulate(
    open_asks: list[float],
    open_probabilities: list[float],
    committed: float,
    goal: float,
    n_trials: int = 10_000,
    seed: int = 42,
) -> ForecastDistribution:
    """Simulate campaign outcomes and return the forecast distribution.

    Args:
        open_asks: Ask amount of each open opportunity.
        open_probabilities: Win probability (0-1) aligned with ``open_asks``.
        committed: Dollars already committed (added to every trial).
        goal: Campaign goal, used for the probability-of-goal estimate.
        n_trials: Number of Monte Carlo trials.
        seed: RNG seed for reproducibility.

    Returns:
        A ``ForecastDistribution`` with committed, P10/P50/P90, mean, and the
        share of trials that reached ``goal``.
    """
    if len(open_asks) != len(open_probabilities):
        raise ValueError("open_asks and open_probabilities must be the same length")

    rng = np.random.default_rng(seed)
    asks = np.asarray(open_asks, dtype=float)
    probs = np.asarray(open_probabilities, dtype=float)

    # (n_trials x n_opps) Bernoulli wins, each weighted by its ask, summed per trial.
    wins = rng.random((n_trials, asks.size)) < probs
    totals = committed + wins @ asks

    return ForecastDistribution(
        committed=round(committed, 0),
        p10=round(float(np.percentile(totals, 10)), 0),
        p50=round(float(np.percentile(totals, 50)), 0),
        p90=round(float(np.percentile(totals, 90)), 0),
        mean=round(float(totals.mean()), 0),
        probability_of_goal=round(float((totals >= goal).mean()), 3),
    )
