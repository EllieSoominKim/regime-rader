"""Orchestration layer for the FastAPI app.

No modeling/allocation math lives here -- every function below wires
together the existing, already-validated modules:
  - GarchXModel (models/garch_x_model.py, copied from kb-balance -- see
    that module's docstring) + ecos_fetch (this repo) for data
  - GaussianHMMFiltered / model_selection / WalkForwardRegimeEngine for
    regime detection
  - RegimeConditionalHRP / WalkForwardHRPEngine for allocation
  - data/backtest_regime_hrp_vs_6040.py and
    data/backtest_synthetic_crash_stress_test.py's own metric functions,
    imported by file path and called directly (not re-derived here) for
    the backtest summary.

Config (candidate_state_counts, selection_criterion, refit_frequency,
min_train_window, n_init, random_state) matches what those scripts already
validated on real data -- see FINDINGS.md.

Fully self-contained within regime-rader: no path into kb-balance, no
dependency on kb-balance's .env. ECOS_API_KEY is loaded from this repo's
own .env by ecos_fetch.py itself (see that module's docstring).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")

# Matches the sys.path convention already used throughout data/*.py: data/
# has no __init__.py (it's a script directory, not a package), so its
# modules are imported as top-level names with data/ itself on sys.path.
# REPO_ROOT is on sys.path for `models.garch_x_model` and every top-level
# module here (filtered_hmm, walk_forward, regime_conditional_hrp, ...).
for _path in (REPO_ROOT, DATA_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from ecos_fetch import fetch_ecos_series  # noqa: E402
from fetch_asset_returns import build_asset_returns_matrix  # noqa: E402
from models.garch_x_model import GarchXModel  # noqa: E402

from filtered_hmm import GaussianHMMFiltered  # noqa: E402
from model_selection import compare_regime_counts  # noqa: E402
from regime_conditional_hrp import RegimeConditionalHRP, WalkForwardHRPEngine  # noqa: E402
from walk_forward import WalkForwardRegimeEngine  # noqa: E402


def _load_module(name: str, filename: str):
    """Import a data/*.py script as a module by file path (not `data.X`,
    since data/ isn't a package) so its metric/construction functions can
    be called directly instead of re-implemented here. Safe: these files
    only run work inside `if __name__ == "__main__"`, so importing them
    executes just their top-level function/constant definitions."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(DATA_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_backtest_mod = _load_module("_backtest_regime_hrp_vs_6040", "backtest_regime_hrp_vs_6040.py")
_synthetic_mod = _load_module("_backtest_synthetic_crash_stress_test", "backtest_synthetic_crash_stress_test.py")

DAYS = 500
KTB_STAT_CODE, KTB_ITEM_CODE = "817Y002", "010200000"
CRISIS_TOP_K = 1

# Same config as data/run_walk_forward_real_ktb.py / run_walk_forward_hrp_real.py.
WALK_FORWARD_CONFIG = dict(
    n_states=2,
    candidate_state_counts=(2, 3),
    selection_criterion="bic",
    refit_frequency="W",
    min_train_window=60,
    n_init=10,
    random_state=0,
)
HRP_CONFIG = dict(refit_frequency="W", min_train_window=60)

# Live single-fit path uses the same candidate/selection/n_init/random_state
# as the walk-forward config so "today" is read the same way the full
# history would read its own most recent day -- just without re-walking
# every historical refit date to get there.
LIVE_CANDIDATE_STATE_COUNTS = WALK_FORWARD_CONFIG["candidate_state_counts"]
LIVE_SELECTION_CRITERION = WALK_FORWARD_CONFIG["selection_criterion"]
LIVE_N_INIT = WALK_FORWARD_CONFIG["n_init"]
LIVE_RANDOM_STATE = WALK_FORWARD_CONFIG["random_state"]


def fetch_ktb_conditional_volatility(days: int = DAYS) -> pd.Series:
    """Same fetch + GARCH-X fit as data/fetch_real_ktb_series.py, as an
    importable function (no CSV round-trip needed for the live API path)."""
    rate_series = fetch_ecos_series(KTB_STAT_CODE, KTB_ITEM_CODE, freq="D", days=days).rename("ktb_3y_yield")
    model = GarchXModel(p=1, q=1)
    model.fit(rate_series)
    cond_vol = model.fitted_model.conditional_volatility
    cond_vol.name = "conditional_volatility"
    cond_vol.index.name = "date"
    return cond_vol


def compute_regime_history(days: int = DAYS) -> pd.DataFrame:
    """Full walk-forward regime detection -- same engine/config as
    data/run_walk_forward_real_ktb.py. This is the ~85s step (94 refits x
    n_init=10 over the current 500-day window)."""
    series = fetch_ktb_conditional_volatility(days=days)
    engine = WalkForwardRegimeEngine(**WALK_FORWARD_CONFIG)
    return engine.run(series)


def compute_hrp_history(regime_history: pd.DataFrame) -> "tuple[pd.DataFrame, pd.DataFrame]":
    """Full walk-forward HRP allocation over regime_history's own
    crisis_probability column -- same engine/config as
    data/run_walk_forward_hrp_real.py. Returns (hrp_df, asset_returns); the
    backtest step needs both."""
    asset_returns = build_asset_returns_matrix(regime_history.index)
    engine = WalkForwardHRPEngine(**HRP_CONFIG)
    hrp_df = engine.run(asset_returns, regime_history["crisis_probability"])
    return hrp_df, asset_returns


def compute_backtest_summary(asset_returns: pd.DataFrame, hrp_history: pd.DataFrame) -> dict:
    """Regime-HRP vs static 60/40 on real data -- reuses
    data/backtest_regime_hrp_vs_6040.py's own static_6040_returns /
    regime_hrp_returns / compute_metrics directly, no re-derivation."""
    mod = _backtest_mod
    weight_cols = [f"weight_{a}" for a in mod.ASSETS]
    valid_hrp = hrp_history.dropna(subset=weight_cols)
    if valid_hrp.empty:
        raise ValueError("No valid HRP-weight rows to backtest")
    start_date, end_date = valid_hrp.index.min(), asset_returns.index.max()

    window = asset_returns.loc[start_date:end_date, mod.ASSETS].copy()
    hrp_weights = valid_hrp.loc[start_date:end_date, weight_cols].rename(columns=lambda c: c.replace("weight_", ""))
    window, hrp_weights = window.align(hrp_weights, join="inner", axis=0)
    window = window.dropna()
    hrp_weights = hrp_weights.loc[window.index]

    bench_ret = mod.static_6040_returns(window)
    hrp_ret = mod.regime_hrp_returns(window, hrp_weights)
    risk_free_annual = float(window["cash"].mean() * mod.TRADING_DAYS)

    full_metrics = {
        "regime_hrp": mod.compute_metrics(hrp_ret, risk_free_annual),
        "benchmark_6040": mod.compute_metrics(bench_ret, risk_free_annual),
    }

    high_mask = (window.index >= mod.HIGH_CRISIS_START) & (window.index <= mod.HIGH_CRISIS_END)
    split_metrics = {}
    for label, mask in [("high_crisis_feb_jun_2026", high_mask), ("rest_of_window", ~high_mask)]:
        if mask.sum() < 5:
            continue
        split_metrics[f"regime_hrp__{label}"] = mod.compute_metrics(hrp_ret[mask], risk_free_annual)
        split_metrics[f"benchmark_6040__{label}"] = mod.compute_metrics(bench_ret[mask], risk_free_annual)

    return {
        "window_start": str(start_date.date()),
        "window_end": str(end_date.date()),
        "n_days": int(len(window)),
        "risk_free_annual": risk_free_annual,
        "full_window": full_metrics,
        "regime_split": split_metrics,
        "assumptions": {
            "benchmark_weights": mod.BENCHMARK_TARGET,
            "benchmark_rebalance": "monthly (first trading day of each calendar month)",
            "regime_hrp_rebalance": "daily (WalkForwardHRPEngine's own target weight per day)",
            "transaction_costs": "not modeled for either strategy",
            "risk_free_source": "cash column (CD 91-day yield accrual) mean, annualized, over the backtest window",
        },
    }


def compute_synthetic_stress_summary(asset_returns: pd.DataFrame, regime_history: pd.DataFrame) -> dict:
    """Synthetic -20%/25-day equity crash spliced into the real crisis
    window -- reuses data/backtest_synthetic_crash_stress_test.py's own
    build_synthetic_crash / metric functions directly. crisis_probability
    is left untouched (it never depended on equity data)."""
    mod = _synthetic_mod
    crisis_probability = regime_history["crisis_probability"]

    crash_series = mod.build_synthetic_crash(asset_returns.index)
    spliced_returns = asset_returns.copy()
    spliced_returns.loc[crash_series.index, "stocks"] = crash_series.values

    engine = WalkForwardHRPEngine(**HRP_CONFIG)
    spliced_hrp = engine.run(spliced_returns, crisis_probability)

    weight_cols = [f"weight_{a}" for a in mod.ASSETS]
    valid_hrp = spliced_hrp.dropna(subset=weight_cols)
    start_date, end_date = valid_hrp.index.min(), spliced_returns.index.max()

    window = spliced_returns.loc[start_date:end_date, mod.ASSETS].copy()
    hrp_weights = valid_hrp.loc[start_date:end_date, weight_cols].rename(columns=lambda c: c.replace("weight_", ""))
    window, hrp_weights = window.align(hrp_weights, join="inner", axis=0)
    window = window.dropna()
    hrp_weights = hrp_weights.loc[window.index]

    bench_ret = mod.static_6040_returns(window)
    hrp_ret = mod.regime_hrp_returns(window, hrp_weights)
    risk_free_annual = float(window["cash"].mean() * mod.TRADING_DAYS)

    full_metrics = {
        "regime_hrp": mod.compute_metrics(hrp_ret, risk_free_annual),
        "benchmark_6040": mod.compute_metrics(bench_ret, risk_free_annual),
    }

    crash_mask = window.index.isin(crash_series.index)
    high_mask = (window.index >= mod.HIGH_CRISIS_START) & (window.index <= mod.HIGH_CRISIS_END)
    split_metrics = {}
    for label, mask in [
        ("crash_window_25d", crash_mask),
        ("high_crisis_feb_jun_2026", high_mask),
        ("rest_of_window", ~high_mask),
    ]:
        if mask.sum() < 3:
            continue
        split_metrics[f"regime_hrp__{label}"] = mod.compute_metrics(hrp_ret[mask], risk_free_annual)
        split_metrics[f"benchmark_6040__{label}"] = mod.compute_metrics(bench_ret[mask], risk_free_annual)

    return {
        "label": "SYNTHETIC STRESS TEST -- NOT REAL HISTORICAL DATA",
        "crash_start": mod.CRASH_START,
        "crash_n_days": mod.CRASH_N_DAYS,
        "crash_total_return_target": mod.CRASH_TOTAL_RETURN,
        "window_start": str(start_date.date()),
        "window_end": str(end_date.date()),
        "risk_free_annual": risk_free_annual,
        "full_window": full_metrics,
        "regime_split": split_metrics,
    }


@dataclass
class DailyBundle:
    regime_history: pd.DataFrame
    hrp_history: pd.DataFrame
    asset_returns: pd.DataFrame
    backtest_summary: dict
    synthetic_stress_summary: dict
    timings: Dict[str, float] = field(default_factory=dict)


def compute_daily_bundle(days: int = DAYS) -> DailyBundle:
    """The single expensive (~85s, dominated by the walk-forward regime
    refit loop) computation shared by all three "history" endpoints
    (regime/history, hrp/history, backtest/summary). Computed at most once
    per calendar day (api/cache.py) under one shared cache key, so the
    three endpoints split one recompute instead of each paying their own."""
    t0 = time.perf_counter()
    regime_history = compute_regime_history(days=days)
    t1 = time.perf_counter()
    hrp_history, asset_returns = compute_hrp_history(regime_history)
    t2 = time.perf_counter()
    backtest_summary = compute_backtest_summary(asset_returns, hrp_history)
    t3 = time.perf_counter()
    synthetic_stress_summary = compute_synthetic_stress_summary(asset_returns, regime_history)
    t4 = time.perf_counter()

    return DailyBundle(
        regime_history=regime_history,
        hrp_history=hrp_history,
        asset_returns=asset_returns,
        backtest_summary=backtest_summary,
        synthetic_stress_summary=synthetic_stress_summary,
        timings={
            "regime_history_seconds": round(t1 - t0, 2),
            "hrp_history_seconds": round(t2 - t1, 2),
            "backtest_summary_seconds": round(t3 - t2, 2),
            "synthetic_stress_seconds": round(t4 - t3, 2),
            "total_seconds": round(t4 - t0, 2),
        },
    )


def compute_today_snapshot(days: int = DAYS) -> dict:
    """Lightweight live path for /api/regime/today: ONE single-shot model
    selection fit over the most recent `days` observations (not the
    94-refit walk-forward loop that makes compute_regime_history ~85s),
    then one RegimeConditionalHRP fit and a single .allocate() call for
    today."""
    series = fetch_ktb_conditional_volatility(days=days)

    comparison = compare_regime_counts(
        series.values,
        state_counts=LIVE_CANDIDATE_STATE_COUNTS,
        n_init=LIVE_N_INIT,
        random_state=LIVE_RANDOM_STATE,
        covariance_type="diag",
    )
    winner = comparison.bic_winner if LIVE_SELECTION_CRITERION == "bic" else comparison.aic_winner
    model: GaussianHMMFiltered = winner.model

    filtered_probs = model.filtered_probabilities(series.values)
    crisis_prob_series = pd.Series(
        model.crisis_probability(filtered_probs, top_k=CRISIS_TOP_K),
        index=series.index,
        name="crisis_probability",
    )
    today_date = series.index[-1]
    today_crisis_probability = float(crisis_prob_series.iloc[-1])
    today_state_probs = filtered_probs[-1]
    today_regime = int(np.argmax(today_state_probs))

    asset_returns = build_asset_returns_matrix(series.index)
    hrp = RegimeConditionalHRP().fit(asset_returns, crisis_prob_series)
    allocation = hrp.allocate(today_crisis_probability)

    return {
        "date": str(today_date.date()),
        "selected_n_states": int(winner.n_states),
        "selection_criterion": LIVE_SELECTION_CRITERION,
        "crisis_probability": today_crisis_probability,
        "regime": today_regime,
        "state_probabilities": [float(p) for p in today_state_probs],
        "recommended_weights": allocation.weights,
        "combined_defensive_weight": float(
            sum(allocation.weights.get(a, 0.0) for a in RegimeConditionalHRP.DEFENSIVE_ASSETS)
        ),
        "effective_n_calm": allocation.effective_n_calm,
        "effective_n_crisis": allocation.effective_n_crisis,
        "calm_covariance_shrunk": allocation.calm_covariance_shrunk,
        "crisis_covariance_shrunk": allocation.crisis_covariance_shrunk,
        "aic_by_candidate": {int(c.n_states): float(c.aic) for c in comparison.candidates},
        "bic_by_candidate": {int(c.n_states): float(c.bic) for c in comparison.candidates},
    }


def df_to_records(df: pd.DataFrame, date_key: str = "date") -> list:
    """DataFrame with a DatetimeIndex -> list of JSON-safe dicts: NaN/NaT/
    pd.NA -> None (checked via pd.isna, so this also handles pandas
    nullable-Int64 columns -- see routers/regime.py's selected_n_states/
    regime casting), numpy scalar types -> native Python, index -> ISO
    date string under `date_key`."""
    records = []
    for idx, row in df.iterrows():
        record = {date_key: idx.date().isoformat() if hasattr(idx, "date") else str(idx)}
        for col, val in row.items():
            if pd.isna(val):
                val = None
            elif isinstance(val, np.integer):
                val = int(val)
            elif isinstance(val, np.floating):
                val = float(val)
            elif isinstance(val, (np.bool_, bool)):
                val = bool(val)
            record[col] = val
        records.append(record)
    return records
