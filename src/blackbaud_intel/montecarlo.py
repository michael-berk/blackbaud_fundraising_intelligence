"""Monte Carlo campaign-forecast simulation.

Models each open opportunity as a Bernoulli trial (wins its full ask with
probability = win_probability, else nothing) and simulates the whole open pipeline
many times. The result is a distribution of campaign totals (P10/P50/P90 and
probability of goal) rather than a single point estimate.

The core ``simulate`` is pure Python so it unit-tests without Spark; the
decision_science notebook feeds it rows from opp_enriched and persists the result.
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
