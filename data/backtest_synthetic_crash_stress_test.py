"""SYNTHETIC STRESS TEST -- NOT REAL HISTORICAL DATA.

Splices a synthetic equity crash into the real asset_returns.csv, timed to
coincide with the real (rate-volatility-derived) Feb-Jun 2026 high-crisis
window, then re-runs the same regime-HRP vs static-60/40 backtest on the
spliced data. This directly tests the MECHANISM -- does regime-HRP's
defensive tilt actually cut a drawdown when an equity crash coincides with
the flagged regime -- which the real 500-day sample couldn't test, since
its one real crisis episode (elevated KTB yield volatility) did not
coincide with an equity selloff (see backtest_regime_hrp_vs_6040.py's
finding: benchmark_6040 returned +119% annualized during that window).

Only the `stocks` column is modified, and only for a 25-trading-day window.
bonds/gold/cash and crisis_probability (derived purely from the KTB yield
series, unaffected by equity data) are the REAL, unmodified series --
crisis_probability is not recomputed here because it was never a function
of equity returns in the first place, so splicing a stock crash doesn't
change what the rate-vol regime engine "sees."
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from regime_conditional_hrp import WalkForwardHRPEngine  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
TRADING_DAYS = 252
ASSETS = ["stocks", "bonds", "cash", "gold"]
BENCHMARK_TARGET = {"stocks": 0.6, "bonds": 0.4, "cash": 0.0, "gold": 0.0}

CRASH_START = "2026-03-02"
CRASH_N_DAYS = 25
CRASH_TOTAL_RETURN = -0.20  # -20%, middle of the requested -15% to -25% range

HIGH_CRISIS_START = "2026-02-01"
HIGH_CRISIS_END = "2026-06-30"


def build_synthetic_crash(index: pd.DatetimeIndex, seed: int = 42) -> pd.Series:
    """A noisy but exactly-calibrated -20% equity decline over 25 trading
    days: sample realistic daily noise, then multiplicatively rescale every
    day by the same constant factor so the compounded total hits
    CRASH_TOTAL_RETURN exactly (preserves realistic day-to-day shape while
    hitting a precise, stated target magnitude).
    """
    crash_dates = index[index >= CRASH_START][:CRASH_N_DAYS]
    rng = np.random.default_rng(seed)
    raw_daily = rng.normal(loc=-0.01, scale=0.015, size=len(crash_dates))
    cum_factor = np.prod(1 + raw_daily)
    target_factor = 1 + CRASH_TOTAL_RETURN
    scale_adjust = (target_factor / cum_factor) ** (1 / len(crash_dates))
    crash_returns = (1 + raw_daily) * scale_adjust - 1
    assert np.isclose(np.prod(1 + crash_returns), target_factor, atol=1e-9)
    return pd.Series(crash_returns, index=crash_dates)


def static_6040_returns(window: pd.DataFrame) -> pd.Series:
    rebalance_dates = set(window.groupby(window.index.to_period("M")).apply(lambda g: g.index.min()))
    weights = np.array([BENCHMARK_TARGET[a] for a in ASSETS])
    returns = []
    for date in window.index:
        if date in rebalance_dates:
            weights = np.array([BENCHMARK_TARGET[a] for a in ASSETS])
        r = window.loc[date, ASSETS].values.astype(float)
        port_r = float(np.dot(weights, r))
        returns.append(port_r)
        weights = weights * (1 + r) / (1 + port_r)
    return pd.Series(returns, index=window.index, name="benchmark_6040")


def regime_hrp_returns(window: pd.DataFrame, hrp_weights: pd.DataFrame) -> pd.Series:
    r = window[ASSETS].values.astype(float)
    w = hrp_weights[ASSETS].values.astype(float)
    return pd.Series((w * r).sum(axis=1), index=window.index, name="regime_hrp")


def compute_metrics(returns: pd.Series, risk_free_annual: float) -> dict:
    cumulative = (1 + returns).cumprod()
    total_return = float(cumulative.iloc[-1] - 1)
    n_days = len(returns)
    annualized_return = float((1 + total_return) ** (TRADING_DAYS / n_days) - 1) if n_days > 0 else np.nan
    annualized_vol = float(returns.std() * np.sqrt(TRADING_DAYS))
    sharpe = (annualized_return - risk_free_annual) / annualized_vol if annualized_vol > 0 else np.nan
    # [2026-08 fix] see the identical fix + full rationale in
    # backtest_regime_hrp_vs_6040.py's compute_metrics -- this is the same
    # duplicated function, same bug, same fix: clamp the running max to
    # never fall below the starting capital of 1.0, so a day-1 loss (in
    # ANY sliced sub-window, including crash_window_25d/high_crisis, each
    # of which restarts this computation at its own first day) registers
    # as a real drawdown instead of silently computing to exactly 0.
    running_max = cumulative.cummax().clip(lower=1.0)
    drawdown = cumulative / running_max - 1
    mdd = float(drawdown.min())
    calmar = annualized_return / abs(mdd) if mdd != 0 else np.nan
    return {
        "n_days": n_days,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_vol": annualized_vol,
        "sharpe": float(sharpe),
        "mdd": mdd,
        "calmar": float(calmar),
    }


def main() -> None:
    print("=" * 70)
    print("SYNTHETIC STRESS TEST -- NOT REAL HISTORICAL DATA")
    print(f"Synthetic equity crash: {CRASH_TOTAL_RETURN:.0%} over {CRASH_N_DAYS} trading days from {CRASH_START}")
    print("=" * 70)

    asset_returns = pd.read_csv(os.path.join(DATA_DIR, "asset_returns.csv"), index_col=0, parse_dates=True)
    regime_output = pd.read_csv(
        os.path.join(DATA_DIR, "walk_forward_real_output.csv"), index_col="date", parse_dates=["date"]
    )
    crisis_probability = regime_output["crisis_probability"]  # REAL, unmodified -- derived from KTB yield only

    crash_series = build_synthetic_crash(asset_returns.index)
    print(f"\nCrash window: {crash_series.index.min().date()} to {crash_series.index.max().date()} "
          f"({len(crash_series)} trading days)")
    print(f"Compounded synthetic stock return over crash window: {(np.prod(1 + crash_series) - 1):.2%}")

    spliced_returns = asset_returns.copy()
    spliced_returns.loc[crash_series.index, "stocks"] = crash_series.values
    spliced_returns.to_csv(os.path.join(DATA_DIR, "synthetic_asset_returns_stress_test.csv"))

    print("\nRe-running WalkForwardHRPEngine on the spliced (synthetic-crash) data "
          "with the REAL, unmodified crisis_probability...")
    engine = WalkForwardHRPEngine(refit_frequency="W", min_train_window=60)
    spliced_hrp_output = engine.run(spliced_returns, crisis_probability)
    spliced_hrp_output.to_csv(os.path.join(DATA_DIR, "synthetic_walk_forward_hrp_output.csv"))

    weight_cols = [f"weight_{a}" for a in ASSETS]
    valid_hrp = spliced_hrp_output.dropna(subset=weight_cols)
    start_date, end_date = valid_hrp.index.min(), spliced_returns.index.max()
    print(f"Backtest window: {start_date.date()} to {end_date.date()}")

    window = spliced_returns.loc[start_date:end_date, ASSETS].copy()
    hrp_weights = valid_hrp.loc[start_date:end_date, weight_cols].rename(columns=lambda c: c.replace("weight_", ""))
    window, hrp_weights = window.align(hrp_weights, join="inner", axis=0)
    window = window.dropna()
    hrp_weights = hrp_weights.loc[window.index]

    bench_ret = static_6040_returns(window)
    hrp_ret = regime_hrp_returns(window, hrp_weights)

    risk_free_annual = float(window["cash"].mean() * TRADING_DAYS)

    full_metrics = {
        "regime_hrp": compute_metrics(hrp_ret, risk_free_annual),
        "benchmark_6040": compute_metrics(bench_ret, risk_free_annual),
    }
    print("\n=== FULL WINDOW (synthetic-crash scenario) ===")
    print(pd.DataFrame(full_metrics).T.to_string())

    crash_mask = window.index.isin(crash_series.index)
    high_mask = (window.index >= HIGH_CRISIS_START) & (window.index <= HIGH_CRISIS_END)

    split_metrics = {}
    for label, mask in [
        ("crash_window_25d", crash_mask),
        ("high_crisis_feb_jun_2026", high_mask),
        ("rest_of_window", ~high_mask),
    ]:
        if mask.sum() < 3:
            continue
        split_metrics[f"regime_hrp__{label}"] = compute_metrics(hrp_ret[mask], risk_free_annual)
        split_metrics[f"benchmark_6040__{label}"] = compute_metrics(bench_ret[mask], risk_free_annual)

    print("\n=== REGIME SPLIT (synthetic-crash scenario) ===")
    print(pd.DataFrame(split_metrics).T.to_string())

    pd.DataFrame({"regime_hrp": hrp_ret, "benchmark_6040": bench_ret}).to_csv(
        os.path.join(DATA_DIR, "synthetic_stress_test_daily_returns.csv")
    )
    with open(os.path.join(DATA_DIR, "synthetic_stress_test_summary.json"), "w") as f:
        json.dump(
            {
                "label": "SYNTHETIC STRESS TEST -- NOT REAL HISTORICAL DATA",
                "crash_start": CRASH_START,
                "crash_n_days": CRASH_N_DAYS,
                "crash_total_return_target": CRASH_TOTAL_RETURN,
                "window_start": str(start_date.date()),
                "window_end": str(end_date.date()),
                "risk_free_annual": risk_free_annual,
                "full_window": full_metrics,
                "regime_split": split_metrics,
            },
            f,
            indent=2,
        )
    print(f"\nSaved to synthetic_stress_test_summary.json / synthetic_stress_test_daily_returns.csv "
          f"(clearly synthetic-prefixed, not to be confused with the real backtest outputs)")


if __name__ == "__main__":
    main()
