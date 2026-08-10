"""Fetch daily return series for the four asset classes RegimeConditionalHRP
needs (stocks/bonds/gold/cash), aligned to the same date index as the
existing WalkForwardRegimeEngine output (data/walk_forward_real_output.csv),
and report basic sanity stats before any HRP code is written.

Sources (all ECOS, via the shared ecos_fetch.fetch_ecos_series helper):
  stocks: 802Y001/0001000  KOSPI index, daily -> pct-change return
  bonds:  817Y002/010200000  3Y KTB yield, daily -> duration-approximated
          return (see convert_yield_to_bond_return)
  cash:   817Y002/010502000  CD(91-day) yield, daily -> running-yield accrual
          (see convert_yield_to_cash_return)
  gold:   902Y003/040101  international gold price (USD/troy oz) -- ECOS
          ONLY carries this at monthly/quarterly/annual cycle, confirmed by
          checking StatisticItemList directly (no daily cycle exists in the
          catalog at all, not just "not found yet"). Fetched at monthly
          cycle and forward-filled to the daily target index -- see the
          sanity-check output for exactly how many days that leaves flat.
          Also NOT converted to KRW (ignores USD/KRW FX effect on a Korean
          investor's realized gold return) -- both are documented
          simplifications, not silent gaps.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecos_fetch import fetch_ecos_series  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DAYS = 500

# Approximate modified duration for a 3Y Korean Treasury Bond trading near
# par -- duration is somewhat less than the 3-year maturity because of
# intervening coupon payments. 2.75 is a standard practitioner rule-of-thumb
# for a ~3% coupon 3-year bond; not fitted to this specific bond's actual
# coupon schedule (a small, documented simplification -- prioritizing speed
# per the Sept 7 scope call).
KTB_3Y_MODIFIED_DURATION = 2.75

# Cash-equivalent (CD 91-day) is modeled as a running-yield accrual, not a
# duration-sensitive price return: unlike a 3-year bond, a continuously-
# rolled 91-day instrument's price risk from yield changes is small enough
# to treat as ~riskless carry for this purpose.
TRADING_DAYS_PER_YEAR = 252


def fetch_stocks_returns(days: int = DAYS) -> pd.Series:
    """KOSPI index (802Y001/0001000), daily -> simple returns."""
    level = fetch_ecos_series("802Y001", "0001000", freq="D", days=days)
    return level.pct_change().dropna().rename("stocks")


def fetch_bonds_returns(days: int = DAYS) -> pd.Series:
    """3Y KTB yield (817Y002/010200000), daily -> duration-approximated
    bond return: return_t = -duration * (yield_t - yield_{t-1}) / 100.
    """
    yield_pct = fetch_ecos_series("817Y002", "010200000", freq="D", days=days)
    return convert_yield_to_bond_return(yield_pct, KTB_3Y_MODIFIED_DURATION).rename("bonds")


def convert_yield_to_bond_return(yield_pct: pd.Series, duration: float) -> pd.Series:
    yield_change = yield_pct.diff().dropna() / 100.0
    return -duration * yield_change


def fetch_cash_returns(days: int = DAYS) -> pd.Series:
    """CD(91-day) yield (817Y002/010502000), daily -> running-yield daily
    accrual: return_t = yield_t / 100 / TRADING_DAYS_PER_YEAR.
    """
    yield_pct = fetch_ecos_series("817Y002", "010502000", freq="D", days=days)
    return convert_yield_to_cash_return(yield_pct).rename("cash")


def convert_yield_to_cash_return(yield_pct: pd.Series) -> pd.Series:
    return yield_pct / 100.0 / TRADING_DAYS_PER_YEAR


def fetch_gold_returns(days: int = DAYS, target_index: pd.DatetimeIndex = None) -> pd.Series:
    """International gold price (902Y003/040101, USD/troy oz), monthly ->
    forward-filled to `target_index` (if given, else the fetched monthly
    dates themselves) -> simple returns. Monthly-resolution proxy: see
    module docstring.
    """
    # ~500 daily obs ~ ~24 months; fetch generously wider so forward-fill
    # has real coverage from before the target window's start.
    monthly_days = max(36, int(days / 20))
    level = fetch_ecos_series("902Y003", "040101", freq="M", days=monthly_days)
    if target_index is not None:
        level = level.reindex(level.index.union(target_index)).sort_index().ffill()
        level = level.reindex(target_index)
    return level.pct_change().rename("gold")


def build_asset_returns_matrix(target_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Fetch all four asset return series and align them to `target_index`
    (intended to be WalkForwardRegimeEngine's own output index, so
    RegimeConditionalHRP consumes exactly the same dates as
    crisis_probability). Returns the raw aligned DataFrame WITHOUT filling
    any remaining NaNs -- alignment gaps should be visible, not silently
    papered over, before anything downstream depends on them.
    """
    stocks = fetch_stocks_returns()
    bonds = fetch_bonds_returns()
    cash = fetch_cash_returns()
    gold = fetch_gold_returns(target_index=target_index)

    df = pd.DataFrame(
        {
            "stocks": stocks.reindex(target_index),
            "bonds": bonds.reindex(target_index),
            "cash": cash.reindex(target_index),
            "gold": gold.reindex(target_index),
        }
    )
    return df


def main() -> None:
    regime_output = pd.read_csv(
        os.path.join(DATA_DIR, "walk_forward_real_output.csv"), index_col="date", parse_dates=["date"]
    )
    target_index = regime_output.index

    print(f"Target window (from walk_forward_real_output.csv): "
          f"{target_index.min().date()} to {target_index.max().date()}, {len(target_index)} dates")

    returns = build_asset_returns_matrix(target_index)

    print("\n=== Sanity stats (pre-fill) ===")
    print(returns.describe().T[["mean", "std", "min", "max"]])

    print("\n=== NaN counts per column ===")
    print(returns.isna().sum())

    print("\n=== Where do NaNs fall? (first/last NaN date per column, if any) ===")
    for col in returns.columns:
        na_dates = returns.index[returns[col].isna()]
        if len(na_dates) > 0:
            print(f"  {col}: {len(na_dates)} NaNs, first={na_dates.min().date()}, last={na_dates.max().date()}")
        else:
            print(f"  {col}: no NaNs")

    print("\n=== Gold forward-fill flatness check ===")
    gold_diff_zero = (returns["gold"] == 0).sum()
    gold_total = returns["gold"].notna().sum()
    print(f"  {gold_diff_zero} / {gold_total} gold-return days are exactly 0.0 "
          f"(flat within a forward-filled month), "
          f"{gold_total - gold_diff_zero} days show a real (month-boundary) move")

    print("\n=== Correlation matrix (pairwise, NaN-dropped) ===")
    print(returns.corr())

    out_path = os.path.join(DATA_DIR, "asset_returns.csv")
    returns.to_csv(out_path)
    print(f"\nSaved asset_returns matrix to {out_path}")


if __name__ == "__main__":
    main()
