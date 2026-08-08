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
