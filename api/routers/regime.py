"""GET /api/regime/history (cached/scheduled), GET /api/regime/today (live).

Both go through api.cache.cache, just under different keys and different
compute functions -- see api/cache.py and api/pipeline.py module docstrings
for the shared "compute once per day, serve cached otherwise" pattern.
"""
from __future__ import annotations

from functools import partial
from typing import Literal

from fastapi import APIRouter

from api.cache import cache
from api.pipeline import compute_daily_bundle, compute_today_snapshot, df_to_records

router = APIRouter(prefix="/api/regime", tags=["regime"])

HISTORY_CACHE_KEY = "daily_bundle"  # shared with routers/hrp.py and routers/backtest.py
TODAY_CACHE_KEY_PREFIX = "regime_today"

# There's no user-accounts/persistence layer in this MVP (see
# RegimeConditionalHRP.RISK_TIERS), so risk_tier travels as a request
# query param, not server-side user state -- the frontend persists the
# user's chosen tier itself (localStorage) and sends it on every request.
RiskTier = Literal["보수적", "중립", "공격적"]

REGIME_HISTORY_COLUMNS = ["crisis_probability", "selected_n_states", "regime", "refit"]


@router.get("/history")
def regime_history():
    result = cache.get_or_compute(HISTORY_CACHE_KEY, compute_daily_bundle)
    bundle = result.value
    history_df = bundle.regime_history[REGIME_HISTORY_COLUMNS].copy()
    # selected_n_states/regime are whole numbers but the column is float64
    # (pandas upcasts the whole column once any row is NaN -- the rows
    # before min_train_window are). Cast to pandas' nullable Int64 so the
    # JSON output is a real int (or null), not e.g. 3.0 -- df_to_records
    # handles the resulting pd.NA the same way it handles NaN.
    history_df["selected_n_states"] = history_df["selected_n_states"].astype("Int64")
    history_df["regime"] = history_df["regime"].astype("Int64")
    records = df_to_records(history_df)
    return {
        "cache_hit": result.cache_hit,
        "computed_on": result.computed_on.isoformat(),
        "compute_seconds": round(result.compute_seconds, 2),
        "n_rows": len(records),
        "history": records,
    }


@router.get("/today")
def regime_today(risk_tier: RiskTier = "중립"):
    # Cache key MUST include risk_tier, not just the trading day -- three
    # tiers means three independent cache entries (still cheap: at most
    # one ~14s single-fit compute per tier per day, not per request), one
    # per (trading_day, risk_tier) pair. Using a flat "regime_today" key
    # here would silently serve one tier's cached allocation to every
    # other tier's request -- exactly the bug this comment is here to
    # prevent a future edit from reintroducing.
    cache_key = f"{TODAY_CACHE_KEY_PREFIX}:{risk_tier}"
    result = cache.get_or_compute(cache_key, partial(compute_today_snapshot, risk_tier=risk_tier))
    return {
        "cache_hit": result.cache_hit,
        "computed_on": result.computed_on.isoformat(),
        "compute_seconds": round(result.compute_seconds, 2),
        **result.value,
    }
