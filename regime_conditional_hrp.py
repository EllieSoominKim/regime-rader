"""Regime-conditional Hierarchical Risk Parity.

Estimates exactly TWO covariance matrices (calm, crisis) from asset-return
history, regardless of how many latent HMM states are currently active (2
or 3, per candidate_state_counts) -- see `RegimeConditionalHRP` docstring
for why this is the state-count-agnostic design point. Allocation blends
those two matrices smoothly by `crisis_probability`
(WalkForwardRegimeEngine's own output column), consistent with that
engine's own finding that crisis_probability is the stable signal across
state-count changes, not raw per-state probabilities.

Clustering/bisection math is copied+adapted from kb-balance's
`hrp_model.py` -- see `hrp_core.py`'s module docstring for exactly what was
reused vs. changed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from hrp_core import (
    apply_allocation_bounds,
    cluster_assets_from_covariance,
    covariance_to_correlation,
    recursive_bisection,
    _get_quasi_diag,
)


def _weighted_covariance(returns: pd.DataFrame, weights: np.ndarray) -> "tuple[pd.DataFrame, float]":
    """Weighted sample covariance + Kish's effective sample size
    (sum(w)^2 / sum(w^2)) for the given weight vector.

    Every historical day contributes to the estimate fractionally,
    proportional to its (already state-count-agnostic) crisis_probability
    or 1-crisis_probability -- no hard threshold/bucket cutoff.
    """
    w = np.asarray(weights, dtype=float)
    w_sum = w.sum()
    n_assets = returns.shape[1]

    if w_sum <= 0:
        # No effective mass at all in this bucket (e.g. crisis_probability
        # was exactly 0 for the entire fit window). Return a
        # zero-information fallback (tiny, uncorrelated variances) and
        # effective_n=0 so the caller's sample-size shrinkage always
        # engages rather than dividing by zero.
        cov = pd.DataFrame(np.eye(n_assets) * 1e-8, index=returns.columns, columns=returns.columns)
        return cov, 0.0

    weighted_mean = (returns.values * w[:, None]).sum(axis=0) / w_sum
    centered = returns.values - weighted_mean
    cov_matrix = (centered * w[:, None]).T @ centered / w_sum
    cov = pd.DataFrame(cov_matrix, index=returns.columns, columns=returns.columns)
    effective_n = float((w_sum ** 2) / (w ** 2).sum())
    return cov, effective_n


def _diagonalize(cov: pd.DataFrame) -> pd.DataFrame:
    """Drop off-diagonal (correlation) structure, keep each asset's own
    variance -- the de-risked fallback for a covariance estimate whose
    effective sample size is too thin to trust its cross-asset structure
    at all, not just its precision.
    """
    return pd.DataFrame(np.diag(np.diag(cov.values)), index=cov.index, columns=cov.columns)


def apply_variance_floor(cov: pd.DataFrame, floor_fraction: float) -> "tuple[pd.DataFrame, List[str]]":
    """Clip each asset's variance to at least `floor_fraction` times this
    matrix's own median asset variance, rescaling that asset's row/column
    so its CORRELATIONS with every other asset are preserved exactly
    (only the diagonal moves) -- naively overwriting just the diagonal
    entry would leave the matrix internally inconsistent (a covariance
    matrix implies its own correlations; you can't change one without the
    other).

    Why a fraction of the median (not a fixed absolute number): the floor
    needs to adapt to which regime's matrix it's applied to -- crisis
    covariances are systematically larger-scale than calm ones, and a
    single hardcoded absolute floor would be irrelevantly small in a
    high-vol crisis matrix or overly binding in a calm one. A floor
    relative to the current matrix's own cross-sectional median variance
    scales automatically with regime. 1% keeps a >=100x variance gap
    between a near-degenerate asset (like cash, whose measured variance
    here is ~1000x smaller than the other three -- see the asset_returns
    sanity check) and a normal one, while preventing HRP's inverse-variance
    weighting from handing it a >=1000x weighting advantage purely from a
    measurement artifact.
    """
    variances = np.diag(cov.values).copy()
    median_var = float(np.median(variances))
    floor = floor_fraction * median_var
    floored: List[str] = []
    cov = cov.copy()
    for i, asset in enumerate(cov.columns):
        if variances[i] < floor:
            floored.append(asset)
            if variances[i] > 0:
                scale = float(np.sqrt(floor / variances[i]))
                cov.iloc[i, :] *= scale
                cov.iloc[:, i] *= scale
            else:
                cov.iloc[i, i] = floor
    return cov, floored


@dataclass
class RegimeConditionalAllocation:
    weights: Dict[str, float]
    blended_covariance: pd.DataFrame
    blended_correlation: pd.DataFrame
    calm_correlation: pd.DataFrame
    crisis_correlation: pd.DataFrame
    crisis_probability_used: float
    effective_n_calm: float
    effective_n_crisis: float
    calm_covariance_shrunk: bool
    crisis_covariance_shrunk: bool
    variance_floor_applied_calm: List[str]
    variance_floor_applied_crisis: List[str]


class RegimeConditionalHRP:
    """Fit two (calm, crisis) covariance matrices from asset-return history
    weighted by crisis_probability, then allocate by blending them.

    State-count-agnostic by construction: `crisis_probability` is already
    defined (by WalkForwardRegimeEngine / GaussianHMMFiltered.crisis_probability)
    as the summed filtered-probability mass of the top-k highest-variance
    canonically-ordered states, independent of how many total states (2 or
    3, or more) the currently-selected model has. This class only ever
    consumes that one scalar per day -- it never looks at n_states or raw
    per-state probabilities -- so a live 2<->3 state-count change at a
    regime-engine refit requires no special-casing here at all.

    Safeguards:
      - Sample-size shrinkage: covariance estimation uses every historical
        day, weighted continuously (not a hard bucket cutoff), but a bucket
        whose Kish effective sample size (sum(w)^2/sum(w^2)) falls below
        MIN_EFFECTIVE_N=30 is not trusted at full strength. 30 is the
        conventional rule-of-thumb minimum for treating a weighted
        mean/covariance as a reasonably stable estimate (the usual
        CLT-adjacent heuristic cited for "is this sample big enough"
        absent a more elaborate power calculation, which is more rigor
        than this competition-scoped build needs). Below that: calm's
        correlation structure is dropped (kept diagonal-only) since it's
        the fallback target for crisis too; crisis is shrunk via convex
        combination toward calm, weight = effective_n_crisis/30 (so a
        crisis bucket with effective_n=0 is 100% calm, effective_n=30 is
        100% trusted).
      - Variance floor: applied to both calm_covariance_ and
        crisis_covariance_ (after sample-size shrinkage, before use in
        clustering/blending) -- see `apply_variance_floor` docstring.

    Known data-quality caveat surfaced here deliberately, not just at the
    fetch layer: the `gold` column (see data/fetch_asset_returns.py) is a
    monthly ECOS series forward-filled to daily -- measured at 95% flat
    days, 5% real month-boundary moves. Any correlation figure here
    involving gold (calm_correlation_, crisis_correlation_, or the
    blended correlation in `allocate()`'s output) is therefore
    structurally biased toward zero on most days by construction (you
    cannot correlate with a literal constant) -- this is NOT evidence that
    gold is actually uncorrelated with the other assets, just a resolution
    artifact of the source data. Keep this in mind before this feeds a
    correlation-breakdown dashboard visualization.

    A SEPARATE gold caveat, distinct from the flat-day dilution above:
    gold's weighted calm/crisis covariance split (`calm_covariance_` vs
    `crisis_covariance_`, and the correlations derived from them) is only
    as reliable as the coincidence of WHEN each month's single real print
    happens to land relative to that month's crisis_probability path. The
    flat-day note above is about correlation being diluted toward zero by
    volume (474 of 498 days contribute nothing); this one is about the 24
    real days being weighted by whatever crisis_probability happened to be
    on that one specific print date, not by gold's actual risk on the days
    it was actually moving in the real world (which forward-fill can't
    recover -- we only ever observe the month's cumulative move, not which
    day within it happened). A gold print landing on a low-crisis day in a
    month that was mostly high-crisis, for instance, would attribute that
    entire month's gold move to the calm bucket instead of crisis, purely
    from timing coincidence. Unlike stocks/bonds/cash, gold's regime split
    here is NOT a smoothly-estimated regime-conditional value -- treat
    `calm_covariance_`/`crisis_covariance_`'s gold entries as considerably
    less trustworthy than the other three assets' entries, independent of
    the flat-day dilution issue.
    """

    MIN_EFFECTIVE_N = 30
    VARIANCE_FLOOR_FRACTION = 0.01

    DEFENSIVE_ASSETS = {"bonds", "cash"}
    CALM_DEFENSIVE_MAX_WEIGHT = 0.5
    CRISIS_DEFENSIVE_MAX_WEIGHT = 0.85
    GROWTH_MAX_WEIGHT = 0.6
    DEFENSIVE_MIN_WEIGHT = 0.05

    # [2026-08 fix] Growth-asset MIN_WEIGHT used to be a single fixed 0.05
    # for every asset, every regime. That silently defeated the whole
    # regime-conditional design: raw (unbounded) inverse-variance HRP
    # weights for stocks/gold in this asset universe are ~0.1-0.3% in BOTH
    # calm and crisis (see the walk-forward finding + the synthetic
    # stress-test check that measured weight_stocks at exactly 0.05 to
    # machine precision on both a calm day and a crash day) -- the fixed
    # 0.05 floor was always the binding constraint, so the crisis-covariance
    # blending and the defensive-cap widening never got a chance to show up
    # in the final weights at all. The demonstrated "crash protection" in
    # that stress test was really just a permanently-defensive static tilt,
    # directly contradicting the design's core differentiator ("정적
    # 글라이드패스가 아닌 국면 인식 기반 동적 조정").
    #
    # Fixed the same way the defensive cap already works: interpolate the
    # growth floor continuously by crisis_probability instead of holding it
    # fixed. CRISIS_GROWTH_MIN_WEIGHT=0.0 at p=1 is deliberate, not an
    # oversight -- observed raw growth-asset weights (~0.1-0.3%) are already
    # below any small positive floor we could pick (even 0.01 would still
    # bind), so the floor has to actually reach 0 for the covariance-driven
    # mechanism and the defensive cap to be the binding constraints instead
    # of this one, which was the whole point of the fix.
    CALM_GROWTH_MIN_WEIGHT = 0.05
    CRISIS_GROWTH_MIN_WEIGHT = 0.0

    def __init__(self) -> None:
        self.asset_names_: Optional[List[str]] = None
        self.calm_covariance_: Optional[pd.DataFrame] = None
        self.crisis_covariance_: Optional[pd.DataFrame] = None
        self.calm_correlation_: Optional[pd.DataFrame] = None
        self.crisis_correlation_: Optional[pd.DataFrame] = None
        self.effective_n_calm_: Optional[float] = None
        self.effective_n_crisis_: Optional[float] = None
        self.calm_covariance_shrunk_: bool = False
        self.crisis_covariance_shrunk_: bool = False
        self.variance_floor_applied_calm_: List[str] = []
        self.variance_floor_applied_crisis_: List[str] = []

    def fit(self, asset_returns: pd.DataFrame, crisis_probability: pd.Series) -> "RegimeConditionalHRP":
        asset_returns, p = asset_returns.align(crisis_probability, join="inner", axis=0)
        valid = asset_returns.notna().all(axis=1) & p.notna()
        asset_returns = asset_returns.loc[valid]
        p = p.loc[valid]
        if len(asset_returns) == 0:
            raise ValueError("No overlapping, non-NaN (asset_returns, crisis_probability) rows to fit on")

        self.asset_names_ = list(asset_returns.columns)
        w_crisis = p.values
        w_calm = 1.0 - w_crisis

        calm_cov_raw, self.effective_n_calm_ = _weighted_covariance(asset_returns, w_calm)
        crisis_cov_raw, self.effective_n_crisis_ = _weighted_covariance(asset_returns, w_crisis)

        if self.effective_n_calm_ < self.MIN_EFFECTIVE_N:
            self.calm_covariance_shrunk_ = True
            calm_cov = _diagonalize(calm_cov_raw)
        else:
            self.calm_covariance_shrunk_ = False
            calm_cov = calm_cov_raw

        if self.effective_n_crisis_ < self.MIN_EFFECTIVE_N:
            self.crisis_covariance_shrunk_ = True
            alpha = max(self.effective_n_crisis_, 0.0) / self.MIN_EFFECTIVE_N
            crisis_cov = alpha * crisis_cov_raw + (1 - alpha) * calm_cov
        else:
            self.crisis_covariance_shrunk_ = False
            crisis_cov = crisis_cov_raw

        calm_cov, self.variance_floor_applied_calm_ = apply_variance_floor(calm_cov, self.VARIANCE_FLOOR_FRACTION)
        crisis_cov, self.variance_floor_applied_crisis_ = apply_variance_floor(crisis_cov, self.VARIANCE_FLOOR_FRACTION)

        self.calm_covariance_ = calm_cov
        self.crisis_covariance_ = crisis_cov
        self.calm_correlation_ = covariance_to_correlation(calm_cov)
        self.crisis_correlation_ = covariance_to_correlation(crisis_cov)
        return self

    def allocate(self, current_crisis_probability: float) -> RegimeConditionalAllocation:
        if self.calm_covariance_ is None:
            raise ValueError("RegimeConditionalHRP must be fit() before allocate()")

        p = float(np.clip(current_crisis_probability, 0.0, 1.0))
        blended_cov = (1 - p) * self.calm_covariance_ + p * self.crisis_covariance_
        blended_corr = covariance_to_correlation(blended_cov)

        _, link = cluster_assets_from_covariance(blended_cov)
        sort_ix = _get_quasi_diag(link)
        sorted_labels = blended_cov.index[sort_ix].tolist()
        raw_weights = recursive_bisection(blended_cov, sorted_labels)

        max_weight = {
            asset: (
                self.CALM_DEFENSIVE_MAX_WEIGHT
                + p * (self.CRISIS_DEFENSIVE_MAX_WEIGHT - self.CALM_DEFENSIVE_MAX_WEIGHT)
                if asset in self.DEFENSIVE_ASSETS
                else self.GROWTH_MAX_WEIGHT
            )
            for asset in self.asset_names_
        }
        min_weight = {
            asset: (
                self.DEFENSIVE_MIN_WEIGHT
                if asset in self.DEFENSIVE_ASSETS
                else self.CALM_GROWTH_MIN_WEIGHT
                + p * (self.CRISIS_GROWTH_MIN_WEIGHT - self.CALM_GROWTH_MIN_WEIGHT)
            )
            for asset in self.asset_names_
        }
        bounded = apply_allocation_bounds(raw_weights.round(4).to_dict(), min_weight=min_weight, max_weight=max_weight)

        return RegimeConditionalAllocation(
            weights=bounded,
            blended_covariance=blended_cov,
            blended_correlation=blended_corr,
            calm_correlation=self.calm_correlation_,
            crisis_correlation=self.crisis_correlation_,
            crisis_probability_used=p,
            effective_n_calm=self.effective_n_calm_,
            effective_n_crisis=self.effective_n_crisis_,
            calm_covariance_shrunk=self.calm_covariance_shrunk_,
            crisis_covariance_shrunk=self.crisis_covariance_shrunk_,
            variance_floor_applied_calm=list(self.variance_floor_applied_calm_),
            variance_floor_applied_crisis=list(self.variance_floor_applied_crisis_),
        )


class WalkForwardHRPEngine:
    """Day-by-day driver for RegimeConditionalHRP, mirroring
    WalkForwardRegimeEngine's own no-look-ahead refit pattern: each periodic
    refit fits only on (asset_returns, crisis_probability) history strictly
    before that date; between refits, `allocate()` is called daily using
    that day's already-forward-filtered crisis_probability.
    """

    def __init__(self, refit_frequency: str = "W", min_train_window: int = 60) -> None:
        self.refit_frequency = refit_frequency
        self.min_train_window = min_train_window

    def run(self, asset_returns: pd.DataFrame, crisis_probability: pd.Series) -> pd.DataFrame:
        common_index = asset_returns.index.intersection(crisis_probability.dropna().index)
        asset_returns = asset_returns.loc[common_index].sort_index()
        crisis_probability = crisis_probability.loc[common_index].sort_index()
        dates = asset_returns.index

        if len(dates) < self.min_train_window + 1:
            raise ValueError("Not enough overlapping data for min_train_window")

        refit_dates = self._compute_refit_dates(dates)
        self.refit_models_: Dict[pd.Timestamp, RegimeConditionalHRP] = {}

        asset_names = list(asset_returns.columns)
        model: Optional[RegimeConditionalHRP] = None
        rows = []

        for current_idx, current_date in enumerate(dates):
            if current_idx < self.min_train_window:
                row = {"date": current_date, "refit": False, "crisis_probability": np.nan}
                row.update({f"weight_{a}": np.nan for a in asset_names})
                row.update(
                    {
                        "effective_n_calm": np.nan,
                        "effective_n_crisis": np.nan,
                        "calm_covariance_shrunk": np.nan,
                        "crisis_covariance_shrunk": np.nan,
                        "variance_floor_applied_calm": "",
                        "variance_floor_applied_crisis": "",
                        "combined_defensive_weight": np.nan,
                        "defensive_mix_shift": np.nan,
                    }
                )
                rows.append(row)
                continue

            if current_date in refit_dates or model is None:
                train_returns = asset_returns.iloc[:current_idx]
                train_p = crisis_probability.iloc[:current_idx]
                model = RegimeConditionalHRP().fit(train_returns, train_p)
                self.refit_models_[current_date] = model
                refit_flag = True
            else:
                refit_flag = False

            todays_p = float(crisis_probability.iloc[current_idx])
            allocation = model.allocate(todays_p)

            row = {"date": current_date, "refit": refit_flag, "crisis_probability": todays_p}
            for asset in asset_names:
                row[f"weight_{asset}"] = allocation.weights.get(asset, np.nan)
            row["effective_n_calm"] = allocation.effective_n_calm
            row["effective_n_crisis"] = allocation.effective_n_crisis
            row["calm_covariance_shrunk"] = allocation.calm_covariance_shrunk
            row["crisis_covariance_shrunk"] = allocation.crisis_covariance_shrunk
            row["variance_floor_applied_calm"] = ",".join(allocation.variance_floor_applied_calm)
            row["variance_floor_applied_crisis"] = ",".join(allocation.variance_floor_applied_crisis)

            # [2026-08] Before the growth-asset floor became
            # regime-responsive (see CALM_GROWTH_MIN_WEIGHT /
            # CRISIS_GROWTH_MIN_WEIGHT), combined bonds+cash weight used to
            # sit pinned at a fixed ~90% ceiling in BOTH calm and crisis
            # periods (driven entirely by the old fixed MIN_WEIGHT=0.05
            # floor on stocks/gold), which on its own read as "the crisis
            # mechanism did nothing" even though the crisis-covariance
            # blending and defensive-cap widening were working correctly
            # underneath -- the only visible regime-responsive signal was
            # the WITHIN-defensive mix (cash vs. bonds). Now that the
            # growth floor itself responds to crisis_probability, combined
            # defensive weight also moves visibly with the regime (see the
            # real-data walk-forward finding: ~0.90 calm -> ~0.996 crisis).
            # `defensive_mix_shift` is kept regardless -- it's still a
            # real, distinct signal (how the defensive sleeve is composed),
            # not just a workaround for the old pinning bug.
            defensive_weight = sum(allocation.weights.get(a, 0.0) for a in RegimeConditionalHRP.DEFENSIVE_ASSETS)
            row["combined_defensive_weight"] = defensive_weight
            row["defensive_mix_shift"] = (
                allocation.weights.get("cash", np.nan) / defensive_weight if defensive_weight > 0 else np.nan
            )
            rows.append(row)

        return pd.DataFrame(rows).set_index("date")

    def _compute_refit_dates(self, dates: pd.DatetimeIndex) -> set:
        # Same pattern as WalkForwardRegimeEngine._compute_refit_dates.
        anchor = dates[0]
        target_dates = pd.date_range(start=anchor, end=dates[-1], freq=self.refit_frequency)
        aligned = []
        for target in target_dates:
            candidates = dates[dates >= target]
            if len(candidates) > 0:
                aligned.append(candidates[0])
        return set(aligned)
