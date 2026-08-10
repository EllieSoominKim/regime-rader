"""Run WalkForwardRegimeEngine on the real 3Y KTB GARCH-X conditional
volatility series (see fetch_real_ktb_series.py) for the first time --
everything before this used synthetic data.

Config (per instructions): candidate_state_counts=(2,3),
selection_criterion='bic', refit_frequency='W', min_train_window=60,
n_init=10, random_state=0 (kept consistent with every synthetic-data run
in this project so far).
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from walk_forward import WalkForwardRegimeEngine  # noqa: E402

DATA_DIR = os.path.dirname(__file__)
IN_PATH = os.path.join(DATA_DIR, "ktb_conditional_volatility.csv")
OUT_PATH = os.path.join(DATA_DIR, "walk_forward_real_output.csv")


def main() -> None:
    series = pd.read_csv(IN_PATH, index_col="date", parse_dates=["date"])["conditional_volatility"]
    series = series.sort_index()
    print(f"Loaded {len(series)} observations, {series.index.min().date()} to {series.index.max().date()}")

    engine = WalkForwardRegimeEngine(
        n_states=2,
        candidate_state_counts=(2, 3),
        selection_criterion="bic",
        refit_frequency="W",
        min_train_window=60,
        n_init=10,
        random_state=0,
    )

    warning_counter: Counter = Counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start = time.perf_counter()
        results = engine.run(series)
        elapsed = time.perf_counter() - start
        for w in caught:
            warning_counter[f"{w.category.__name__}: {str(w.message)[:120]}"] += 1

    results.to_csv(OUT_PATH)

    # --- 1. Refit / state-count-change counts ---
    refit_rows = results[results["refit"]]
    n_refits = int(len(refit_rows))
    selected_at_refits = refit_rows["selected_n_states"].astype(int)

    boundaries = []
    prev = None
    for idx, val in selected_at_refits.items():
        if prev is not None and val != prev:
            prior_date = results.index[results.index.get_loc(idx) - 1]
            jump = abs(results.loc[idx, "crisis_probability"] - results.loc[prior_date, "crisis_probability"])
            boundaries.append(
                {
                    "date": str(idx.date()),
                    "prior_date": str(prior_date.date()),
                    "from_n_states": int(prev),
                    "to_n_states": int(val),
                    "crisis_prob_prior": float(results.loc[prior_date, "crisis_probability"]),
                    "crisis_prob_at_boundary": float(results.loc[idx, "crisis_probability"]),
                    "jump": float(jump),
                }
            )
        prev = val

    # --- 2. Monthly crisis_probability summary ---
    monthly = (
        results["crisis_probability"]
        .dropna()
        .resample("MS")
        .agg(["mean", "min", "max", "count"])
    )

    summary = {
        "n_rows": int(len(results)),
        "date_range": [str(results.index.min().date()), str(results.index.max().date())],
        "elapsed_seconds": round(elapsed, 2),
        "n_refits": n_refits,
        "n_state_count_changes": len(boundaries),
        "selected_n_states_unique_at_refits": sorted(int(x) for x in selected_at_refits.unique()),
        "boundaries": boundaries,
        "warning_counts": dict(warning_counter),
        "total_warnings": int(sum(warning_counter.values())),
    }

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))

    print("\n=== MONTHLY crisis_probability ===")
    print(monthly.to_string())

    print(f"\nSaved full walk-forward output ({len(results)} rows) to {OUT_PATH}")

    with open(os.path.join(DATA_DIR, "walk_forward_real_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    monthly.to_csv(os.path.join(DATA_DIR, "walk_forward_real_monthly_crisis_probability.csv"))


if __name__ == "__main__":
    main()
