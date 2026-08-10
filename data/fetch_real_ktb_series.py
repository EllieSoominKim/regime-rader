"""Fetch the real 3Y KTB yield series and fit GARCH-X to produce a
conditional-volatility series for WalkForwardRegimeEngine, on real (not
synthetic) data.

This intentionally does NOT live in / modify the kb-balance project. It
reuses that project's existing data source and model (per the ECOS API key
already configured there) but keeps the trading-day dates that
`kb_balance.server.services.market_data.fetch_market_rate_history` itself
discards (it returns `list[float]`, no index) -- WalkForwardRegimeEngine
requires a real `pd.DatetimeIndex`.

Source: ECOS (한국은행) stat table 817Y002 ("시장금리(일별)"), item code
010200000 (국고채 3년물 / 3Y KTB), freq "D" -- identical request shape to
kb-balance's `fetch_market_rate_history(days=500)`.

Model: GarchXModel(p=1, q=1) from kb-balance's
`server/models/garch_x_model.py` (vol="Garch", dist="normal", no exog),
fit on `rate_series.diff().dropna() * 100` (scaled daily yield changes) --
same as the earlier smoke test.

Run with kb-balance's venv (has `arch`/`requests`/`python-dotenv`, which
regime-rader's venv intentionally does not):
    C:/kb-balance/server/venv/Scripts/python.exe data/fetch_real_ktb_series.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd
from dotenv import load_dotenv

KB_BALANCE_SERVER = r"C:\kb-balance\server"
sys.path.insert(0, KB_BALANCE_SERVER)
load_dotenv(dotenv_path=os.path.join(KB_BALANCE_SERVER, ".env"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecos_fetch import fetch_ecos_series  # noqa: E402
from models.garch_x_model import GarchXModel  # noqa: E402

DAYS = 500
OUT_PATH = os.path.join(os.path.dirname(__file__), "ktb_conditional_volatility.csv")


def fetch_ktb_3y_with_dates(days: int = DAYS) -> pd.Series:
    """3Y KTB yield (817Y002/010200000), daily, most recent `days`
    observations. Thin wrapper over the shared `ecos_fetch.fetch_ecos_series`
    -- see that module's docstring for the 2026-08 pagination-bug fix this
    depends on (list_total_count-based "last N", not "first N").
    """
    return fetch_ecos_series("817Y002", "010200000", freq="D", days=days).rename("ktb_3y_yield")


def main() -> None:
    rate_series = fetch_ktb_3y_with_dates(DAYS)
    print(f"Fetched {len(rate_series)} raw 3Y KTB yield observations, "
          f"{rate_series.index.min().date()} to {rate_series.index.max().date()}")

    model = GarchXModel(p=1, q=1)
    model.fit(rate_series)

    cond_vol = model.fitted_model.conditional_volatility
    cond_vol.name = "conditional_volatility"
    cond_vol.index.name = "date"

    print(f"Fitted GARCH(1,1) conditional volatility: {len(cond_vol)} observations, "
          f"{cond_vol.index.min().date()} to {cond_vol.index.max().date()}")
    print(cond_vol.describe())

    cond_vol.to_csv(OUT_PATH)
    print(f"\nSaved conditional volatility series to {OUT_PATH}")


if __name__ == "__main__":
    main()
