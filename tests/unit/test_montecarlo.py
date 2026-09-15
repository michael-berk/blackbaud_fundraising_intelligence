import pytest

from blackbaud_intel.montecarlo import simulate


def test_certain_wins_sum_to_committed_plus_all_asks():
    dist = simulate(
        open_asks=[100.0, 200.0],
        open_probabilities=[1.0, 1.0],
        committed=50.0,
        goal=1000.0,
        n_trials=1000,
    )
    # Every opp always wins: total is deterministic at 50 + 100 + 200 = 350.
    assert dist.p10 == dist.p50 == dist.p90 == 350.0
    assert dist.probability_of_goal == 0.0


def test_certain_losses_equal_committed():
    dist = simulate([100.0, 200.0], [0.0, 0.0], committed=500.0, goal=100.0, n_trials=1000)
    assert dist.p50 == 500.0
    assert dist.probability_of_goal == 1.0  # committed alone already clears goal


def test_percentiles_are_ordered_for_random_pipeline():
    dist = simulate(
        open_asks=[1000.0] * 20,
        open_probabilities=[0.5] * 20,
        committed=0.0,
        goal=10000.0,
        n_trials=5000,
    )
    assert dist.p10 <= dist.p50 <= dist.p90
    assert 0.0 <= dist.probability_of_goal <= 1.0


def test_reproducible_with_seed():
    args = {"open_asks": [100.0], "open_probabilities": [0.5], "committed": 0.0, "goal": 50.0}
    assert simulate(**args, seed=7) == simulate(**args, seed=7)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError, match="same length"):
        simulate([100.0], [0.5, 0.5], committed=0.0, goal=1.0)
