from __future__ import annotations

import numpy as np
import pytest
from filtered_hmm import GaussianHMMFiltered


def generate_synthetic_two_state_data(n_samples: int = 1000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    states = np.zeros(n_samples, dtype=int)
    obs = np.empty(n_samples, dtype=float)

    current_state = 0
    for t in range(n_samples):
        states[t] = current_state
        obs[t] = rng.normal(loc=-4.0 if current_state == 0 else 4.0, scale=0.2)
        if rng.random() < 0.01:
            current_state = 1 - current_state
    return obs, states


def generate_separable_two_state_data(n_samples: int = 800, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    block_size = 100
    n_blocks = n_samples // block_size
    obs = np.empty(n_samples, dtype=float)
    states = np.empty(n_samples, dtype=int)
    for block in range(n_blocks):
        state = block % 2
        start = block * block_size
        end = start + block_size
        states[start:end] = state
        obs[start:end] = rng.normal(loc=-10.0 if state == 0 else 10.0, scale=0.1, size=block_size)
    return obs, states


def _map_binary_states(true_states: np.ndarray, inferred_states: np.ndarray) -> np.ndarray:
    if np.mean(inferred_states == true_states) >= 0.5:
        return inferred_states
    return 1 - inferred_states


def test_filtered_probability_is_forward_only():
    obs, _ = generate_synthetic_two_state_data(n_samples=200, seed=0)
    model = GaussianHMMFiltered(n_states=2, random_state=0, n_iter=50)
    model.fit(obs)

    filtered_full = model.filtered_probabilities(obs)
    filtered_truncated = model.filtered_probabilities(obs[:100])

    assert np.allclose(filtered_full[:100], filtered_truncated, atol=1e-12, rtol=0)


def test_sanity_recover_two_regimes():
    obs, true_states = generate_synthetic_two_state_data(n_samples=500, seed=1)
    model = GaussianHMMFiltered(n_states=2, random_state=1, n_iter=100)
    model.fit(obs)
    filt = model.filtered_probabilities(obs)
    inferred_states = np.argmax(filt, axis=1)
    inferred_states = _map_binary_states(true_states, inferred_states)

    accuracy = np.mean(inferred_states == true_states)
    assert accuracy > 0.8


def test_fit_is_deterministic_across_runs_with_multiple_restarts():
    """Regression test for a restart-seeding bug: `fit` used to reset
    `self.model.random_state = None` for every restart after the first when
    `n_init > 1`, so restarts 1..n_init-1 drew entropy from OS randomness
    instead of `self.random_state`. The same (random_state, n_init) could
    then silently select a different "best of n_init" local optimum on every
    call — non-determinism that only showed up with n_init > 1 (n_init=1 was
    always reproducible, since it never took the buggy branch).

    Fitting the same data with the same random_state and n_init > 1 twice
    must therefore yield bit-for-bit identical log-likelihood and fitted
    parameters (means, covariances) every time, not just on average.
    """
    obs, _ = generate_synthetic_two_state_data(n_samples=300, seed=3)

    obs_2d = obs.reshape(-1, 1)
    model_a = GaussianHMMFiltered(n_states=2, random_state=3, n_iter=100, n_init=10)
    model_a.fit(obs)
    model_b = GaussianHMMFiltered(n_states=2, random_state=3, n_iter=100, n_init=10)
    model_b.fit(obs)

    assert model_a.model.score(obs_2d) == model_b.model.score(obs_2d)
    assert np.array_equal(model_a.model.means_, model_b.model.means_)
    assert np.array_equal(np.asarray(model_a.model.covars_), np.asarray(model_b.model.covars_))
    assert np.array_equal(model_a.model.transmat_, model_b.model.transmat_)
    assert np.array_equal(model_a.model.startprob_, model_b.model.startprob_)


def test_aic_bic_prefers_true_state_count():
    obs, _ = generate_separable_two_state_data(n_samples=800, seed=2)
    model2 = GaussianHMMFiltered(n_states=2, random_state=2, n_iter=200, n_init=10)
    model3 = GaussianHMMFiltered(n_states=3, random_state=2, n_iter=200, n_init=10)
    model2.fit(obs)
    model3.fit(obs)

    aic2 = model2.aic(obs)
    bic2 = model2.bic(obs)
    aic3 = model3.aic(obs)
    bic3 = model3.bic(obs)

    assert model2.n_parameters() == 7
    assert model3.n_parameters() == 14
    assert bic2 < bic3
    assert aic2 < aic3
