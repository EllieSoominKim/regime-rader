"""GARCH volatility model for the 3Y KTB yield series.

Origin: copied from kb-balance's `server/models/garch_x_model.py`
(originally "GARCH-X 금리 변동성 예측 모델" -- a rate-volatility model with an
optional news-sentiment exogenous regressor). Copied by value, not imported
across repos -- same reasoning as `hrp_core.py`'s copy of kb-balance's HRP
math: `api/pipeline.py` and `data/fetch_real_ktb_series.py` need this to run
standalone (deployment, judges running this repo, anyone without
kb-balance checked out at a specific local path), so a hardcoded
cross-repo import was a blocker, not just a style preference.

What's here vs. the original:
  - `__init__` and `fit()` are unchanged -- this is exactly what both
    `fetch_real_ktb_series.py` and `api/pipeline.py` call
    (`GarchXModel(p=1, q=1).fit(rate_series)`, then read
    `.fitted_model.conditional_volatility`).
  - NOT copied: `predict_hike_probability` (frames its output as a
    "rate hike" probability specific to kb-balance's rate-scenario feature)
    and `build_exog_from_news` (reads `news_df` shaped by kb-balance's own
    FinBERT sentiment pipeline at `services/news_sentiment.py`, which does
    not exist in this repo). Neither is called anywhere in regime-rader --
    this project only ever uses the fitted conditional volatility itself,
    not a hike-probability simulation or a news-sentiment exogenous
    regressor.
  - NOT copied: `predict_volatility` (horizon-ahead volatility forecast).
    Also unused here -- regime-rader consumes the in-sample
    `conditional_volatility` series directly (see `fit()`'s docstring),
    never a forward forecast. Left out rather than carried along unused,
    same as `hrp_core.py` dropping kb-balance methods that don't apply to
    this project's asset universe.
  - `exog` support in `fit()` is kept (harmless pass-through, `None` by
    default) even though regime-rader never passes it, so this stays a
    faithful copy of the one method actually in use rather than a further
    trimmed reinterpretation of it.
"""
from __future__ import annotations

import pandas as pd
from arch import arch_model


class GarchXModel:
    def __init__(self, p: int = 1, q: int = 1):
        self.p = p
        self.q = q
        self.fitted_model = None
        self.rate_series = None

    def fit(self, rate_series: pd.Series, exog: pd.DataFrame = None):
        """
        rate_series: 금리(또는 금리 변화율) 시계열, index는 날짜
        exog: 외생변수 DataFrame (예: news_sentiment, news_volume), rate_series와 같은 index
        """
        self.rate_series = rate_series
        returns = rate_series.diff().dropna() * 100  # 변화율 스케일링 (arch 라이브러리 안정성용)

        model = arch_model(
            returns,
            x=exog.loc[returns.index] if exog is not None else None,
            vol="Garch",
            p=self.p,
            q=self.q,
            dist="normal",
        )
        self.fitted_model = model.fit(disp="off")
        return self
