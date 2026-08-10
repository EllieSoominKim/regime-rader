from __future__ import annotations

import numpy as np
import model_selection
from model_selection import compare_regime_counts
from filtered_hmm import GaussianHMMFiltered


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


def test_degenerate_guard_flags_near_duplicate_states_but_not_genuinely_distinct_ones(monkeypatch):
    """Exercise the degenerate-state guard's `degenerate_variance_rel_tol`
    (default 0.05, i.e. 5%) decision boundary directly, at the two separations
    that bracket it:

    - ~3% relative variance separation (below the 5% tolerance) -> the guard
      must flag the 3-state candidate as degenerate and disqualify it
      (aic/bic bumped to +inf, so the 2-state candidate wins on BIC).
    - ~7% relative variance separation (above the 5% tolerance) -> the guard
      must NOT flag it; the 3-state candidate keeps its real, finite aic/bic.

    In both cases the two near-duplicate states are also given (near-)
    identical means, so only the variance-ratio branch of the guard is being
    exercised, not the mean-separation branch.

    `GaussianHMMFiltered.fit` is subclassed to run a real EM fit (so
    `model.score`/`aic`/`bic` reflect genuine, internally-consistent hmmlearn
    state) and then overwrite `state_variances_`/`means_` with the exact
    prescribed separation afterward, so the test doesn't depend on a
    real EM fit happening to land on a precise variance ratio.
    """
    obs = generate_synthetic_two_state_data(n_samples=300, seed=11)

    def compare_with_forced_variance_ratio(rel_separation: float):
        class _ForcedVarianceModel(GaussianHMMFiltered):
            def fit(self, obs_inner):
                super().fit(obs_inner)
                if self.n_states == 3:
                    base_var = float(self.state_variances_[0])
                    near_dup_var = base_var * (1.0 + rel_separation)
                    self.state_variances_ = np.array(
                        [base_var, near_dup_var, base_var * 25.0]
                    )
                    means = np.asarray(self.model.means_, dtype=float).copy()
                    means[1] = means[0] + 1e-3
                    self.model.means_ = means
                return self

        monkeypatch.setattr(model_selection, "GaussianHMMFiltered", _ForcedVarianceModel)
        return compare_regime_counts(obs, state_counts=(2, 3), n_init=3, random_state=11, n_iter=100)

    result_3pct = compare_with_forced_variance_ratio(0.03)
    candidate_3_at_3pct = next(c for c in result_3pct.candidates if c.n_states == 3)
    assert candidate_3_at_3pct.degenerate is True
    assert candidate_3_at_3pct.aic == float("inf")
    assert candidate_3_at_3pct.bic == float("inf")
    assert result_3pct.bic_winner.n_states == 2

    result_7pct = compare_with_forced_variance_ratio(0.07)
    candidate_3_at_7pct = next(c for c in result_7pct.candidates if c.n_states == 3)
    assert candidate_3_at_7pct.degenerate is False
    assert candidate_3_at_7pct.aic != float("inf")
    assert candidate_3_at_7pct.bic != float("inf")
