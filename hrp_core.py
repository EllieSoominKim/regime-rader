"""Generic (asset-class-agnostic) Hierarchical Risk Parity math.

Origin: copied and adapted from kb-balance's `server/models/hrp_model.py`
(`자산-부채 통합 HRP`, an asset-liability HRP for a personal-finance app).
That file's `_correlation_distance`, `_get_quasi_diag`, `_get_cluster_var`,
`recursive_bisection`, and `apply_allocation_bounds` are already generic
correlation/covariance-clustering math with no loan-specific coupling, so
they're copied here near-verbatim. NOT copied: `build_return_matrix` and
`adjust_for_rate_scenario`, which are specific to that project's synthetic
"loan repayment" pseudo-asset and GARCH-X hike-probability nudge -- neither
concept applies to a stocks/bonds/gold/cash regime-conditional allocation.

Copied by value, not imported across repos, per this project's own scope
(competition submission -- a hardcoded path into a sibling project would
break for anyone else running this code). See regime_conditional_hrp.py for
how this module is used.

What changed from the original:
  - `cluster_assets` (kb-balance) took a *return matrix* and called
    `.corr()` on it. Here, `cluster_assets_from_covariance` instead takes a
    *covariance matrix* directly (RegimeConditionalHRP estimates calm/crisis
    covariances via a weighted formula, not by slicing a return matrix and
    calling `.corr()`), and derives the correlation matrix from it via
    `covariance_to_correlation`.
  - `apply_allocation_bounds`'s `max_weight` now also accepts a per-asset
    dict (not just a single scalar for every asset), because the design
    calls for a wider cap on defensive assets (bonds/cash) that widens
    further with crisis_probability -- kb-balance's version only ever
    needed one global cap.
"""
from __future__ import annotations

from typing import Dict, List, Tuple, Union

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def covariance_to_correlation(cov: pd.DataFrame) -> pd.DataFrame:
    std = np.sqrt(np.diag(cov.values))
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = cov.values / np.outer(std, std)
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)


def _correlation_distance(corr: pd.DataFrame) -> pd.DataFrame:
    # unchanged from kb-balance/hrp_model.py
    return np.sqrt((0.5 * (1 - corr)).clip(lower=0))


def cluster_assets_from_covariance(cov: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
    """Adapted from kb-balance's `cluster_assets`: takes a covariance matrix
    directly instead of a return matrix (see module docstring)."""
    corr = covariance_to_correlation(cov)
    dist = _correlation_distance(corr)
    condensed = squareform(dist.values, checks=False)
    link = linkage(condensed, method="single")
    return corr, link


def _get_quasi_diag(link) -> list:
    # unchanged from kb-balance/hrp_model.py
    link = link.astype(int)
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    num_items = link[-1, 3]
    while sort_ix.max() >= num_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= num_items]
        i = df0.index
        j = df0.values - num_items
        sort_ix[i] = link[j, 0]
        df1 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df1])
        sort_ix = sort_ix.sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.tolist()


def _get_cluster_var(cov: pd.DataFrame, items: list) -> float:
    # unchanged from kb-balance/hrp_model.py
    sub_cov = cov.loc[items, items]
    weights = 1 / np.diag(sub_cov)
    weights /= weights.sum()
    return float(weights @ sub_cov.values @ weights)


def recursive_bisection(cov: pd.DataFrame, sort_ix: list) -> pd.Series:
    # unchanged from kb-balance/hrp_model.py
    weights = pd.Series(1.0, index=sort_ix)
    clusters = [sort_ix]

    while len(clusters) > 0:
        clusters = [
            c[start:end]
            for c in clusters
            for start, end in ((0, len(c) // 2), (len(c) // 2, len(c)))
            if len(c) > 1
        ]
        for i in range(0, len(clusters), 2):
            if i + 1 >= len(clusters):
                continue
            left, right = clusters[i], clusters[i + 1]
            var_left = _get_cluster_var(cov, left)
            var_right = _get_cluster_var(cov, right)
            alpha = 1 - var_left / (var_left + var_right)
            weights[left] *= alpha
            weights[right] *= 1 - alpha

    return weights / weights.sum()


def apply_allocation_bounds(
    weights: Dict[str, float],
    min_weight: Union[float, Dict[str, float]] = 0.05,
    max_weight: Union[float, Dict[str, float]] = 0.7,
) -> Dict[str, float]:
    """Adapted from kb-balance's `apply_allocation_bounds`: `min_weight`/
    `max_weight` now each accept either a single scalar (applied to every
    asset, the original behavior) or a per-asset dict (needed here so
    defensive assets get a different, crisis_probability-dependent cap than
    growth assets -- see module docstring).

    Bug fix vs. the original: the original committed EVERY bound-violating
    asset found in a pass as "fixed" using one stale, un-cascaded
    redistribution snapshot. When floor- and cap-violators occurred in the
    SAME pass (e.g. three assets simultaneously below min_weight while a
    fourth was above max_weight -- exactly what real fits under
    RegimeConditionalHRP produce, see the walk-forward finding that
    stocks/gold pin at MIN_WEIGHT while cash pins at its cap), every asset
    could get locked to a bound in one shot with nothing left "free" to
    absorb the leftover mass, so final weights silently summed to LESS
    than 1 (caught by test_regime_conditional_hrp.py). Fixed by resolving
    one violator at a time -- the most-violated one -- redistributing the
    freed remainder among what's still open before re-checking the rest,
    which is the standard greedy water-filling approach.
    """
    keys = list(weights.keys())
    vals = dict(weights)
    fixed: dict = {}
    free = set(keys)

    def _bound(b: Union[float, Dict[str, float]], key: str) -> float:
        return b[key] if isinstance(b, dict) else b

    while free:
        remaining = 1 - sum(fixed.values())
        free_keys = list(free)
        free_sum = sum(vals[k] for k in free_keys)
        if free_sum <= 0:
            for k in free_keys:
                vals[k] = remaining / len(free_keys)
        else:
            for k in free_keys:
                vals[k] = vals[k] / free_sum * remaining

        worst_key = None
        worst_bound = None
        worst_excess = 0.0
        for k in free_keys:
            lo, hi = _bound(min_weight, k), _bound(max_weight, k)
            if vals[k] > hi and (vals[k] - hi) > worst_excess:
                worst_key, worst_bound, worst_excess = k, hi, vals[k] - hi
            elif vals[k] < lo and (lo - vals[k]) > worst_excess:
                worst_key, worst_bound, worst_excess = k, lo, lo - vals[k]

        if worst_key is None:
            break

        fixed[worst_key] = worst_bound
        free.discard(worst_key)

    result = {**fixed, **{k: vals[k] for k in free}}
    return {k: round(result[k], 4) for k in keys}
