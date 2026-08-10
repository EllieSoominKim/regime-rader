from __future__ import annotations

import numpy as np
import pandas as pd

from regime_conditional_hrp import RegimeConditionalHRP, _weighted_covariance


def test_crisis_covariance_is_shrunk_toward_calm_when_effective_n_is_thin():
    """Regression test for the sample-size-shrinkage safeguard: with only a
    short burst of high-crisis_probability days, effective_n_crisis_ should
    fall below MIN_EFFECTIVE_N, crisis_covariance_shrunk_ should fire, and
    -- the part a flag alone wouldn't prove -- the STORED crisis_covariance_
    should actually have moved toward calm_covariance_, not just gotten
    flagged while staying equal to the raw (noisy) estimate.
    """
    rng = np.random.default_rng(1)
    n = 400
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    assets = ["stocks", "bonds"]

    returns = rng.normal(scale=0.01, size=(n, 2))

    p = np.full(n, 0.01)
    crisis_idx = np.arange(n - 12, n - 2)  # 10 days of real crisis signal
    p[crisis_idx] = 0.95
    # Make those days genuinely higher-variance, so a raw (unshrunk) crisis
    # covariance would look very different from calm if shrinkage didn't
    # actually pull it back.
    returns[crisis_idx] = rng.normal(scale=0.08, size=(len(crisis_idx), 2))

    asset_returns = pd.DataFrame(returns, index=dates, columns=assets)
    crisis_probability = pd.Series(p, index=dates)

    model = RegimeConditionalHRP().fit(asset_returns, crisis_probability)

    assert model.effective_n_crisis_ < RegimeConditionalHRP.MIN_EFFECTIVE_N
    assert model.crisis_covariance_shrunk_ is True
    assert model.calm_covariance_shrunk_ is False  # plenty of calm-day history (effective_n well above 30)

    # Recompute the raw (unshrunk) crisis covariance the same way fit() does
    # internally, purely to compare against what actually got stored.
    crisis_cov_raw, _ = _weighted_covariance(asset_returns, crisis_probability.values)

    def total_variance(cov: pd.DataFrame) -> float:
        return float(np.trace(cov.values))

    # By construction, the raw crisis estimate is much riskier than calm...
    assert total_variance(crisis_cov_raw) > total_variance(model.calm_covariance_) * 3
    # ...but the stored crisis_covariance_ sits strictly between calm and
    # the raw crisis estimate -- i.e. shrinkage actually pulled it down.
    assert total_variance(model.crisis_covariance_) < total_variance(crisis_cov_raw)
    assert total_variance(model.crisis_covariance_) > total_variance(model.calm_covariance_)


def test_variance_floor_lifts_near_degenerate_asset_variance():
    """Regression test for the variance floor: an asset whose measured
    variance is ~1000x smaller than the others (like real cash -- see the
    asset_returns sanity check) should get its variance clipped up to
    VARIANCE_FLOOR_FRACTION * median in BOTH calm_covariance_ and
    crisis_covariance_, and named in the corresponding
    variance_floor_applied_* list.
    """
    rng = np.random.default_rng(2)
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    asset_returns = pd.DataFrame(
        {
            "stocks": rng.normal(scale=0.02, size=n),
            "bonds": rng.normal(scale=0.005, size=n),
            "cash": rng.normal(scale=0.00002, size=n),  # near-degenerate, like real cash
        },
        index=dates,
    )
    # Spread crisis_probability enough that both buckets get a healthy
    # effective sample size -- isolates the variance floor from the
    # sample-size shrinkage safeguard.
    crisis_probability = pd.Series(rng.uniform(0, 1, size=n), index=dates)

    model = RegimeConditionalHRP().fit(asset_returns, crisis_probability)

    assert model.effective_n_calm_ >= RegimeConditionalHRP.MIN_EFFECTIVE_N
    assert model.effective_n_crisis_ >= RegimeConditionalHRP.MIN_EFFECTIVE_N
    assert "cash" in model.variance_floor_applied_calm_
    assert "cash" in model.variance_floor_applied_crisis_

    # Compare against the PRE-floor median, recomputed independently via the
    # same weighted-covariance formula fit() uses internally -- comparing
    # against the POST-floor matrix's own median is slightly circular with
    # few assets (the floored value itself measurably shifts the median).
    w_calm = 1.0 - crisis_probability.values
    w_crisis = crisis_probability.values
    calm_cov_raw, _ = _weighted_covariance(asset_returns, w_calm)
    crisis_cov_raw, _ = _weighted_covariance(asset_returns, w_crisis)

    for cov, cov_raw in ((model.calm_covariance_, calm_cov_raw), (model.crisis_covariance_, crisis_cov_raw)):
        pre_floor_median = float(np.median(np.diag(cov_raw.values)))
        expected_floor = RegimeConditionalHRP.VARIANCE_FLOOR_FRACTION * pre_floor_median
        cash_var = cov.loc["cash", "cash"]
        assert cash_var >= expected_floor - 1e-12
        assert cash_var <= expected_floor * 1.5  # rescale should land close to the target, not far past it


def test_growth_asset_floor_is_regime_responsive_not_pinned():
    """Regression test for a real bug: MIN_WEIGHT used to be a single fixed
    value (0.05) applied to every asset regardless of regime, which
    silently pinned stocks/gold at that floor in BOTH calm and crisis
    allocations -- discovered via a synthetic stress test that measured
    weight_stocks at exactly 0.05 (to machine precision) on both a calm day
    and a crash day, meaning the whole regime-conditional mechanism never
    showed up in the final weights at all despite working correctly
    underneath (crisis-covariance blending, defensive-cap widening).
    Fixed by making the growth-asset floor itself interpolate by
    crisis_probability, symmetric to the existing defensive cap.

    Two checks, not one: the class constants must actually differ (the
    cheap canary that would catch someone collapsing them back to one
    value), AND that difference must actually be wired into allocate()'s
    real output, not just defined-and-unused.
    """
    assert (
        RegimeConditionalHRP.CALM_GROWTH_MIN_WEIGHT - RegimeConditionalHRP.CRISIS_GROWTH_MIN_WEIGHT > 0.02
    ), "CALM_GROWTH_MIN_WEIGHT and CRISIS_GROWTH_MIN_WEIGHT must differ meaningfully, not collapse to one constant"

    rng = np.random.default_rng(4)
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    returns = pd.DataFrame(
        {
            "stocks": rng.normal(scale=0.02, size=n),
            "bonds": rng.normal(scale=0.005, size=n),
            "cash": rng.normal(scale=0.0005, size=n),
            "gold": rng.normal(scale=0.015, size=n),
        },
        index=dates,
    )
    crisis_probability = pd.Series(rng.uniform(0, 1, size=n), index=dates)

    model = RegimeConditionalHRP().fit(returns, crisis_probability)

    calm_alloc = model.allocate(0.0)
    crisis_alloc = model.allocate(1.0)

    for asset in ("stocks", "gold"):
        # Not just "different" -- different by a meaningful margin, so a
        # regression back to a single hardcoded floor (which would produce
        # an exact or near-exact match between the two calls, as it did
        # before this fix) actually fails this assertion.
        assert calm_alloc.weights[asset] - crisis_alloc.weights[asset] > 0.02, (
            f"{asset}: calm={calm_alloc.weights[asset]}, crisis={crisis_alloc.weights[asset]} "
            "-- growth-asset weight should drop measurably as crisis_probability rises"
        )


def test_allocate_defensive_cap_widens_with_crisis_probability():
    """Regression test for allocate()'s per-asset defensive-cap widening,
    tested directly (not via the aggregate bonds+cash total, which can pin
    at a fixed MIN_WEIGHT-driven ceiling regardless of regime -- see the
    real-data walk-forward finding): calling allocate() at p=0 vs p=1 on
    the SAME fitted model should keep each defensive asset within its own
    (widening) cap, and push at least one of them meaningfully higher at
    p=1 than at p=0.
    """
    rng = np.random.default_rng(3)
    n = 300
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    returns = pd.DataFrame(
        {
            "stocks": rng.normal(scale=0.02, size=n),
            "bonds": rng.normal(scale=0.005, size=n),
            "cash": rng.normal(scale=0.0005, size=n),
            "gold": rng.normal(scale=0.015, size=n),
        },
        index=dates,
    )
    crisis_probability = pd.Series(rng.uniform(0, 1, size=n), index=dates)

    model = RegimeConditionalHRP().fit(returns, crisis_probability)

    calm_alloc = model.allocate(0.0)
    crisis_alloc = model.allocate(1.0)

    for asset in RegimeConditionalHRP.DEFENSIVE_ASSETS:
        assert calm_alloc.weights[asset] <= RegimeConditionalHRP.CALM_DEFENSIVE_MAX_WEIGHT + 1e-6
        assert crisis_alloc.weights[asset] <= RegimeConditionalHRP.CRISIS_DEFENSIVE_MAX_WEIGHT + 1e-6

    # The wider cap should actually be doing something, not just be present
    # and unused: at least one defensive asset should sit strictly higher
    # at p=1 than at p=0.
    assert any(
        crisis_alloc.weights[asset] > calm_alloc.weights[asset] + 1e-6
        for asset in RegimeConditionalHRP.DEFENSIVE_ASSETS
    )

    for asset in ("stocks", "gold"):
        assert calm_alloc.weights[asset] <= RegimeConditionalHRP.GROWTH_MAX_WEIGHT + 1e-6
        assert crisis_alloc.weights[asset] <= RegimeConditionalHRP.GROWTH_MAX_WEIGHT + 1e-6

    for alloc in (calm_alloc, crisis_alloc):
        assert np.isclose(sum(alloc.weights.values()), 1.0, atol=1e-3)
