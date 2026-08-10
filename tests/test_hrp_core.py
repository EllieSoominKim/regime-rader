from __future__ import annotations

import numpy as np
import pandas as pd

from hrp_core import (
    apply_allocation_bounds,
    cluster_assets_from_covariance,
    recursive_bisection,
    _get_quasi_diag,
)


def test_hrp_core_pipeline_runs_end_to_end_and_respects_scalar_bounds():
    """Smoke test: cluster_assets_from_covariance -> _get_quasi_diag ->
    recursive_bisection -> apply_allocation_bounds runs without error on
    simple synthetic data, and produces weights that sum to 1 and respect
    a single global min/max bound (the original kb-balance behavior).
    """
    rng = np.random.default_rng(0)
    assets = ["a", "b", "c", "d"]
    returns = rng.normal(size=(300, 4)) @ np.diag([0.01, 0.02, 0.005, 0.03])
    returns[:, 1] += 0.5 * returns[:, 0]  # induce a real correlation
    cov = pd.DataFrame(np.cov(returns, rowvar=False), index=assets, columns=assets)

    corr, link = cluster_assets_from_covariance(cov)
    assert corr.shape == (4, 4)
    assert np.allclose(np.diag(corr.values), 1.0)

    sort_ix = _get_quasi_diag(link)
    sorted_labels = cov.index[sort_ix].tolist()
    assert set(sorted_labels) == set(assets)

    raw_weights = recursive_bisection(cov, sorted_labels)
    assert np.isclose(raw_weights.sum(), 1.0)
    assert (raw_weights > 0).all()

    bounded = apply_allocation_bounds(raw_weights.round(4).to_dict(), min_weight=0.05, max_weight=0.7)
    assert np.isclose(sum(bounded.values()), 1.0, atol=1e-3)
    for w in bounded.values():
        assert w >= 0.05 - 1e-9
        assert w <= 0.7 + 1e-9


def test_apply_allocation_bounds_supports_per_asset_dict_bounds():
    """The adaptation from kb-balance's original (scalar-only) version:
    min_weight/max_weight each accept a per-asset dict, needed so defensive
    assets can have a different (crisis_probability-dependent) cap than
    growth assets.
    """
    weights = {"a": 0.1, "b": 0.1, "c": 0.1, "d": 0.7}
    bounded = apply_allocation_bounds(
        weights,
        min_weight={"a": 0.05, "b": 0.05, "c": 0.05, "d": 0.05},
        max_weight={"a": 0.6, "b": 0.6, "c": 0.6, "d": 0.5},
    )
    assert bounded["d"] <= 0.5 + 1e-9
    assert np.isclose(sum(bounded.values()), 1.0, atol=1e-3)
    for w in bounded.values():
        assert w >= 0.05 - 1e-9
