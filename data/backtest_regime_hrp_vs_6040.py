"""Backtest regime-conditional HRP against a static 60/40 benchmark.

Design-doc feature #4: "백테스팅 및 성과 시각화... 정적 60/40 벤치마크 대비
MDD·샤프비율". Compares WalkForwardHRPEngine's ACTUAL daily weight output
(already computed on real KTB/KOSPI/CD91/gold data) against a static 60%
stocks / 40% bonds benchmark, monthly-rebalanced.

Assumptions, stated explicitly rather than buried in code:
  - 60/40 = stocks/bonds ONLY (gold and cash weighted 0). "60/40" is a
    conventional equity/bond benchmark; folding gold/cash in would no
    longer be a recognizable 60/40 and there's no standard convention for
    where to put them, so they're excluded rather than guessed at.
  - 60/40 rebalances on the first trading day of each calendar month,
    drifting with market moves between rebalances (the standard treatment
    of a "static" periodically-rebalanced benchmark) -- this is NOT the
    same treatment as regime-HRP, which is applied as a fresh daily target
    weight each day (that's what WalkForwardHRPEngine.allocate() already
    produces: a recomputed daily allocation, not a drift-and-hold
    position). That asymmetry is the intended contrast (active
    regime-aware daily adaptation vs. a passive periodic baseline), not an
    inconsistency.
  - NEITHER strategy models transaction costs. This is generous to
    regime-HRP in particular, since it's implicitly assumed to rebalance
    daily for free, which a real deployment would not get.
  - Risk-free rate for Sharpe = the `cash` column's own mean daily return
    (CD 91-day yield accrual), annualized, over the same backtest window --
    an actual observed short-term KRW rate, not an arbitrary constant.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
TRADING_DAYS = 252
ASSETS = ["stocks", "bonds", "cash", "gold"]
BENCHMARK_TARGET = {"stocks": 0.6, "bonds": 0.4, "cash": 0.0, "gold": 0.0}

HIGH_CRISIS_START = "2026-02-01"
HIGH_CRISIS_END = "2026-06-30"


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
    annualized_return = float((1 + total_return) ** (TRADING_DAYS / n_days) - 1)
    annualized_vol = float(returns.std() * np.sqrt(TRADING_DAYS))
    sharpe = (annualized_return - risk_free_annual) / annualized_vol if annualized_vol > 0 else np.nan
    running_max = cumulative.cummax()
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
    asset_returns = pd.read_csv(os.path.join(DATA_DIR, "asset_returns.csv"), index_col=0, parse_dates=True)
    hrp_output = pd.read_csv(
        os.path.join(DATA_DIR, "walk_forward_hrp_real_output.csv"), index_col="date", parse_dates=["date"]
    )

    weight_cols = [f"weight_{a}" for a in ASSETS]
    valid_hrp = hrp_output.dropna(subset=weight_cols)
    start_date, end_date = valid_hrp.index.min(), asset_returns.index.max()
    print(f"Backtest window (starts once regime-HRP has valid daily weights): "
          f"{start_date.date()} to {end_date.date()}, {len(asset_returns.loc[start_date:end_date])} days")

    window = asset_returns.loc[start_date:end_date, ASSETS].copy()
    hrp_weights = valid_hrp.loc[start_date:end_date, weight_cols].rename(columns=lambda c: c.replace("weight_", ""))
    window, hrp_weights = window.align(hrp_weights, join="inner", axis=0)
    window = window.dropna()
    hrp_weights = hrp_weights.loc[window.index]

    bench_ret = static_6040_returns(window)
    hrp_ret = regime_hrp_returns(window, hrp_weights)

    risk_free_annual = float(window["cash"].mean() * TRADING_DAYS)
    print(f"Risk-free rate used for Sharpe (annualized mean cash/CD91 return over window): {risk_free_annual:.4%}")

    full_metrics = {
        "regime_hrp": compute_metrics(hrp_ret, risk_free_annual),
        "benchmark_6040": compute_metrics(bench_ret, risk_free_annual),
    }

    print("\n=== FULL WINDOW ===")
    print(pd.DataFrame(full_metrics).T)

    # --- regime split: high-crisis (Feb-Jun 2026) vs the rest ---
    high_mask = (window.index >= HIGH_CRISIS_START) & (window.index <= HIGH_CRISIS_END)
    split_metrics = {}
    for label, mask in [("high_crisis_feb_jun_2026", high_mask), ("rest_of_window", ~high_mask)]:
        if mask.sum() < 5:
            continue
        split_metrics[f"regime_hrp__{label}"] = compute_metrics(hrp_ret[mask], risk_free_annual)
        split_metrics[f"benchmark_6040__{label}"] = compute_metrics(bench_ret[mask], risk_free_annual)

    print("\n=== REGIME SPLIT (high-crisis Feb-Jun 2026 vs rest) ===")
    print(pd.DataFrame(split_metrics).T)

    # save
    combined_returns = pd.DataFrame({"regime_hrp": hrp_ret, "benchmark_6040": bench_ret})
    combined_returns.to_csv(os.path.join(DATA_DIR, "backtest_daily_returns.csv"))

    with open(os.path.join(DATA_DIR, "backtest_summary.json"), "w") as f:
        json.dump(
            {
                "window_start": str(start_date.date()),
                "window_end": str(end_date.date()),
                "n_days": len(window),
                "risk_free_annual": risk_free_annual,
                "full_window": full_metrics,
                "regime_split": split_metrics,
                "assumptions": {
                    "benchmark_weights": BENCHMARK_TARGET,
                    "benchmark_rebalance": "monthly (first trading day of each calendar month)",
                    "regime_hrp_rebalance": "daily (WalkForwardHRPEngine's own target weight per day)",
                    "transaction_costs": "not modeled for either strategy",
                    "risk_free_source": "cash column (CD 91-day yield accrual) mean, annualized, over the backtest window",
                },
            },
            f,
            indent=2,
        )
    print(f"\nSaved daily returns to {os.path.join(DATA_DIR, 'backtest_daily_returns.csv')}")
    print(f"Saved summary to {os.path.join(DATA_DIR, 'backtest_summary.json')}")


if __name__ == "__main__":
    main()
