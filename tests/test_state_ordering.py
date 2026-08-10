from __future__ import annotations

import numpy as np
import pandas as pd
from filtered_hmm import GaussianHMMFiltered


def generate_synthetic_two_state_series(n_samples: int = 300, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    change_point = n_samples // 2
    values = np.empty(n_samples, dtype=float)
    for t in range(n_samples):
        values[t] = rng.normal(loc=-2.0, scale=0.2) if t < change_point else rng.normal(loc=2.0, scale=0.2)
    return values


def test_state_ordering_is_canonical_by_variance():
    obs = generate_synthetic_two_state_series(seed=42)
    seeds = [0, 1, 2, 3, 4]
    variances = []

    for seed in seeds:
        model = GaussianHMMFiltered(n_states=2, random_state=seed, n_iter=100, n_init=5)
        model.fit(obs)
        state_vars = model._compute_state_variances()
        variances.append(state_vars)

    for state_vars in variances:
        assert state_vars[0] <= state_vars[1]

    for earlier, later in zip(variances, variances[1:]):
        assert earlier[0] <= earlier[1]
        assert later[0] <= later[1]


def generate_synthetic_unequal_variance_series(n_samples: int = 400, seed: int = 0) -> np.ndarray:
    """Two states with distinctly different variances (unlike the equal-variance
    helper above), so a regression that collapses per-state variance to a
    shared average — or that reorders means_/transmat_ but silently fails to
    reorder covars_ for a non-identity permutation — actually shows up as a
    failed assertion instead of trivially passing.
    """
    rng = np.random.default_rng(seed)
    change_point = n_samples // 2
    values = np.empty(n_samples, dtype=float)
    for t in range(n_samples):
        values[t] = rng.normal(loc=-2.0, scale=0.1) if t < change_point else rng.normal(loc=2.0, scale=1.5)
    return values


def test_state_variances_are_genuinely_per_state_after_canonicalization():
    """Regression test for two related bugs found when fitting real (non-toy)
    data: (1) `_compute_state_variances` falling through to an averaged-scalar
    fallback for `covariance_type="diag"` on hmmlearn's (n_states, n_features,
    n_features) covars_ shape, and (2) `_canonicalize_state_order` silently
    failing to reorder covars_ itself (via a swallowed ValueError from
    hmmlearn's covars_ setter shape mismatch) whenever a real, non-identity
    permutation was needed. Both bugs left `state_variances_` looking
    self-consistent while `_compute_state_variances()` recomputed from the
    live model disagreed — so this asserts that recomputation matches the
    stored attribute, not just that it happens to be ascending.
    """
    obs = generate_synthetic_unequal_variance_series(seed=7)

    for seed in range(6):
        model = GaussianHMMFiltered(n_states=2, random_state=seed, n_iter=100, n_init=5)
        model.fit(obs)

        recomputed = model._compute_state_variances()
        assert np.allclose(model.state_variances_, recomputed), (
            f"seed={seed}: stored state_variances_={model.state_variances_} "
            f"disagrees with a fresh _compute_state_variances() call "
            f"({recomputed}) — covars_ was not actually reordered to match "
            f"means_/transmat_/startprob_."
        )
        # The two states were generated with clearly different variances
        # (0.1**2 vs 1.5**2), so canonical order must be a real, non-trivial
        # low-to-high sort, not a coincidental identity permutation.
        assert model.state_variances_[0] < model.state_variances_[1]
        assert model.state_variances_[1] / max(model.state_variances_[0], 1e-12) > 5
