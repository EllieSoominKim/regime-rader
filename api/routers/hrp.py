"""GET /api/hrp/history (cached/scheduled)."""
from __future__ import annotations

from fastapi import APIRouter

from api.cache import cache
from api.pipeline import compute_daily_bundle, df_to_records

router = APIRouter(prefix="/api/hrp", tags=["hrp"])

HISTORY_CACHE_KEY = "daily_bundle"  # shared with routers/regime.py and routers/backtest.py


@router.get("/history")
def hrp_history():
    result = cache.get_or_compute(HISTORY_CACHE_KEY, compute_daily_bundle)
    bundle = result.value
    records = df_to_records(bundle.hrp_history)
    return {
        "cache_hit": result.cache_hit,
        "computed_on": result.computed_on.isoformat(),
        "compute_seconds": round(result.compute_seconds, 2),
        "n_rows": len(records),
        "history": records,
    }
