"""GET /api/backtest/summary (cached/scheduled)."""
from __future__ import annotations

from fastapi import APIRouter

from api.cache import cache
from api.pipeline import compute_daily_bundle

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

HISTORY_CACHE_KEY = "daily_bundle"  # shared with routers/regime.py and routers/hrp.py


@router.get("/summary")
def backtest_summary():
    result = cache.get_or_compute(HISTORY_CACHE_KEY, compute_daily_bundle)
    bundle = result.value
    return {
        "cache_hit": result.cache_hit,
        "computed_on": result.computed_on.isoformat(),
        "compute_seconds": round(result.compute_seconds, 2),
        "real_backtest": bundle.backtest_summary,
        "synthetic_stress_test": bundle.synthetic_stress_summary,
    }
