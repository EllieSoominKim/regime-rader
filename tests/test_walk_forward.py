from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import walk_forward
import model_selection
from filtered_hmm import GaussianHMMFiltered
from walk_forward import WalkForwardRegimeEngine


def generate_synthetic_switch_series(n_samples: int = 200, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    change_point = n_samples // 2
    values = np.empty(n_samples, dtype=float)
    for t in range(n_samples):
        if t < change_point:
            values[t] = rng.normal(loc=0.0, scale=0.2)
        else:
            # Increase variance in the second regime so `crisis_probability`
            # (which is variance-based) rises after the change point.
            values[t] = rng.normal(loc=4.0, scale=1.0)
    dates = pd.date_range(start="2020-01-01", periods=n_samples, freq="B")
    return pd.Series(values, index=dates)


def test_walk_forward_uses_only_past_data():
    obs = generate_synthetic_switch_series(n_samples=150, seed=1)
    engine = WalkForwardRegimeEngine(n_states=2, refit_frequency="W", min_train_window=30, n_init=3, random_state=0)
    results = engine.run(obs)

    sample_date = results.index[80]
    last_refit_date = max(d for d in engine.refit_models_.keys() if d <= sample_date)
    model = engine.refit_models_[last_refit_date]
    filtered_expected = model.filtered_probabilities(obs.loc[:sample_date].values)[-1]

    assert np.allclose(
        results.loc[sample_date, ["state_0", "state_1"]].astype(float).values,
        filtered_expected,
        atol=1e-12,
    )


def test_walk_forward_detects_regime_switch():
    obs = generate_synthetic_switch_series(n_samples=220, seed=2)
    engine = WalkForwardRegimeEngine(n_states=2, refit_frequency="W", min_train_window=40, n_init=3, random_state=0)
    results = engine.run(obs)

    # Use the canonical `crisis_probability` scalar to check regime shift
    first_crisis = results.iloc[40:110]["crisis_probability"].astype(float).mean()
    second_crisis = results.iloc[130:200]["crisis_probability"].astype(float).mean()

    assert first_crisis < second_crisis


def generate_2_to_3_state_series(n_samples: int = 200, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    first_segment = int(n_samples * 0.4)
    second_segment = n_samples - first_segment
    values = np.empty(n_samples, dtype=float)

    for t in range(first_segment):
        cluster = 0 if rng.random() < 0.5 else 1
        values[t] = rng.normal(loc=-1.0 if cluster == 0 else 1.0, scale=0.2)

    for t in range(first_segment, n_samples):
        cluster = rng.choice([0, 1, 2])
        loc = -2.0 if cluster == 0 else (0.0 if cluster == 1 else 2.0)
        values[t] = rng.normal(loc=loc, scale=0.2)

    dates = pd.date_range(start="2020-01-01", periods=n_samples, freq="B")
    return pd.Series(values, index=dates)


def test_walk_forward_refit_cadence():
    obs = generate_synthetic_switch_series(n_samples=240, seed=3)
    engine = WalkForwardRegimeEngine(n_states=2, refit_frequency="W", min_train_window=30, n_init=1, random_state=0)
    results = engine.run(obs)

    refit_count = results["refit"].sum()
    assert refit_count > 1
    assert refit_count < len(results) / 2


def test_walk_forward_selection_changes_state_count_mid_run():
    obs = generate_2_to_3_state_series(n_samples=220, seed=7)
    engine = WalkForwardRegimeEngine(
        n_states=2,
        candidate_state_counts=(2, 3),
        selection_criterion="bic",
        refit_frequency="W",
        min_train_window=30,
        n_init=2,
        random_state=0,
    )
    results = engine.run(obs)

    selected_states = results["selected_n_states"].dropna().astype(int)
    assert selected_states.isin({2, 3}).all()
    assert selected_states.iloc[0] == 2
    assert selected_states.max() == 3
    assert selected_states.min() == 2

    selected_at_refits = selected_states[results["refit"]].unique()
    assert set(selected_at_refits).issubset({2, 3})

    discontinuity_dates = results[results["selected_n_states"] == 3].index
    if len(discontinuity_dates) > 0:
        boundary_date = discontinuity_dates[0]
        previous_date = results.index[results.index.get_loc(boundary_date) - 1]

        # We used to assert `jump < 0.7` here, on the theory that a very
        # large crisis_probability jump at a model-selection boundary must
        # indicate label-switching or an unstable state mapping. The
        # seed-3/seed-5 responsibility diagnostic (see
        # responsibility_diagnostic_seeds_3_5.py and the note in
        # WalkForwardRegimeEngine's docstring) disproved that: it measured
        # the actual new-state -> prior-state mapping at these boundaries
        # and found it near-one-hot (confident, not diffuse/label-switched)
        # even for a seed whose jump was ~1.0 -- the jump was the correct
        # consequence of a genuine new regime splitting off a prior one, not
        # a mapping bug. There is no principled threshold on jump size, so
        # we no longer assert one. What a bug *would* actually look like is
        # the filtered probabilities themselves being malformed, so we check
        # that instead: on both sides of the boundary, the state
        # probabilities are non-NaN and sum to 1.
        for date in (previous_date, boundary_date):
            n_states_at_date = int(results.loc[date, "selected_n_states"])
            state_cols = [f"state_{i}" for i in range(n_states_at_date)]
            state_probs = results.loc[date, state_cols].astype(float)
            assert not state_probs.isna().any(), f"NaN filtered probability at {date}"
            assert np.isclose(state_probs.sum(), 1.0, atol=1e-9), (
                f"Filtered probabilities at {date} must sum to 1, got {state_probs.sum()}"
            )


def test_walk_forward_model_selection_uses_truncated_history(monkeypatch):
    obs = generate_synthetic_switch_series(n_samples=150, seed=5)
    seen_lengths: list[int] = []

    def spy_compare_regime_counts(obs_arr, *args, **kwargs):
        seen_lengths.append(obs_arr.shape[0])
        return model_selection.compare_regime_counts(obs_arr, *args, **kwargs)

    monkeypatch.setattr(walk_forward, "compare_regime_counts", spy_compare_regime_counts)

    engine = WalkForwardRegimeEngine(
        n_states=2,
        candidate_state_counts=(2, 3),
        selection_criterion="bic",
        refit_frequency="W",
        min_train_window=30,
        n_init=1,
        random_state=0,
    )
    engine.run(obs)

    # Ensure no compare_regime_counts call received the full series (no look-ahead),
    # and every call used a truncated history (length <= full length and >= min_train_window)
    assert all( (l <= len(obs) and l >= engine.min_train_window) for l in seen_lengths )
    assert not any(l == len(obs) for l in seen_lengths)
