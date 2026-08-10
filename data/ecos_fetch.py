"""Shared ECOS (한국은행) StatisticSearch fetch helper.

Centralizes the two-call, list_total_count-based "most recent N
observations" fetch pattern (see the 2026-08 pagination-bug writeup in
kb-balance's market_data.fetch_market_rate_history and this project's
fetch_real_ktb_series.py) so every asset-class fetcher in this project
reuses one implementation of that fix instead of copies drifting apart.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

KB_BALANCE_ENV = r"C:\kb-balance\server\.env"
load_dotenv(dotenv_path=KB_BALANCE_ENV)
ECOS_API_KEY = os.getenv("ECOS_API_KEY")
if not ECOS_API_KEY:
    raise RuntimeError(f"ECOS_API_KEY not found in {KB_BALANCE_ENV}")

# Calendar days needed per requested observation, by ECOS cycle code, sized
# generously so the query window always contains at least `days` real
# observations even after weekends/holidays (daily) or reporting lag
# (monthly/quarterly/annual).
_CALENDAR_DAYS_PER_OBS = {"D": 1.6, "M": 45, "Q": 130, "A": 400}


def fetch_ecos_series(
    stat_code: str,
    item_code: str,
    freq: str = "D",
    days: int = 500,
    calendar_buffer_days: Optional[int] = None,
) -> pd.Series:
    """Fetch the most recent `days` observations of stat_code/item_code at
    ECOS cycle `freq` ('D' daily, 'M' monthly, 'Q' quarterly, 'A' annual).

    Returns the LAST `days` rows in ascending date order, not the first --
    `list_total_count` is read first specifically to avoid the pagination
    bug where `1/{days}` silently returns the oldest `days` rows in the
    query window instead of the most recent.
    """
    end = datetime.now()
    if calendar_buffer_days is None:
        calendar_buffer_days = int(days * _CALENDAR_DAYS_PER_OBS.get(freq, 1.6)) + 30
    start = end - timedelta(days=calendar_buffer_days)
    end_s = end.strftime("%Y%m%d")
    start_s = start.strftime("%Y%m%d")
    if freq == "M":
        end_s, start_s = end_s[:6], start_s[:6]
    elif freq == "A":
        end_s, start_s = end_s[:4], start_s[:4]

    def _url(start_row: int, end_row: int) -> str:
        return (
            f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS_API_KEY}/json/kr/"
            f"{start_row}/{end_row}/{stat_code}/{freq}/{start_s}/{end_s}/{item_code}"
        )

    count_res = requests.get(_url(1, 1), timeout=15)
    count_res.raise_for_status()
    count_payload = count_res.json()
    if "StatisticSearch" not in count_payload:
        raise RuntimeError(f"Unexpected ECOS response for {stat_code}/{item_code}: {count_payload}")
    total_count = int(count_payload["StatisticSearch"]["list_total_count"])
    if total_count == 0:
        raise RuntimeError(f"No ECOS data for {stat_code}/{item_code} ({freq}) in window {start_s}-{end_s}")

    n = min(days, total_count)
    start_row = total_count - n + 1
    res = requests.get(_url(start_row, total_count), timeout=15)
    res.raise_for_status()
    rows = res.json()["StatisticSearch"]["row"]

    if freq == "D":
        dates = pd.to_datetime([r["TIME"] for r in rows], format="%Y%m%d")
    elif freq == "M":
        dates = pd.to_datetime([r["TIME"] for r in rows], format="%Y%m") + pd.offsets.MonthBegin(0)
    elif freq == "Q":
        dates = pd.PeriodIndex([r["TIME"] for r in rows], freq="Q").to_timestamp()
    elif freq == "A":
        dates = pd.to_datetime([r["TIME"] for r in rows], format="%Y")
    else:
        raise ValueError(f"Unsupported freq: {freq}")

    values = [float(r["DATA_VALUE"]) for r in rows]
    series = pd.Series(values, index=dates, name=item_code).sort_index()
    series = series[~series.index.duplicated(keep="last")]
    return series
