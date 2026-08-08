from __future__ import annotations

import numpy as np
from model_selection import compare_regime_counts


def generate_synthetic_two_state_data(n_samples: int = 1000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    states = np.zeros(n_samples, dtype=int)
    obs = np.empty(n_samples, dtype=float)

    current_state = 0
    for t in range(n_samples):
        states[t] = current_state
        obs[t] = rng.normal(loc=-4.0 if current_state == 0 else 4.0, scale=0.2)
        if rng.random() < 0.01:
            current_state = 1 - current_state
    return obs


def test_compare_regime_counts_prefers_two_states():
    obs = generate_synthetic_two_state_data(n_samples=800, seed=123)
    result = compare_regime_counts(obs, state_counts=(2, 3), n_init=5, random_state=1, n_iter=100)

    assert result.aic_winner.n_states == 2
    assert result.bic_winner.n_states == 2
    assert all(candidate.n_states in (2, 3) for candidate in result.candidates)
    assert any(candidate.model for candidate in result.candidates)
