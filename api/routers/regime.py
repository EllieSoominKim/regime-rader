"""GET /api/regime/history (cached/scheduled), GET /api/regime/today (live).

Both go through api.cache.cache, just under different keys and different
compute functions -- see api/cache.py and api/pipeline.py module docstrings
for the shared "compute once per day, serve cached otherwise" pattern.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.cache import cache
from api.pipeline import compute_daily_bundle, compute_today_snapshot, df_to_records

router = APIRouter(prefix="/api/regime", tags=["regime"])

HISTORY_CACHE_KEY = "daily_bundle"  # shared with routers/hrp.py and routers/backtest.py
TODAY_CACHE_KEY = "regime_today"

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
def regime_today():
    result = cache.get_or_compute(TODAY_CACHE_KEY, compute_today_snapshot)
    return {
        "cache_hit": result.cache_hit,
        "computed_on": result.computed_on.isoformat(),
        "compute_seconds": round(result.compute_seconds, 2),
        **result.value,
    }
