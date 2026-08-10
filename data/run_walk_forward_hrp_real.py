"""Run WalkForwardHRPEngine on the real asset_returns.csv (stocks/bonds/gold/
cash) + the existing real-KTB WalkForwardRegimeEngine output's
crisis_probability column, and report allocation behavior, safeguard
activity, and any warnings.
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from regime_conditional_hrp import WalkForwardHRPEngine  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    asset_returns = pd.read_csv(os.path.join(DATA_DIR, "asset_returns.csv"), index_col=0, parse_dates=True)
    regime_output = pd.read_csv(
        os.path.join(DATA_DIR, "walk_forward_real_output.csv"), index_col="date", parse_dates=["date"]
    )
    crisis_probability = regime_output["crisis_probability"]

    print(f"asset_returns: {asset_returns.shape}, {asset_returns.index.min().date()} to {asset_returns.index.max().date()}")
    print(f"crisis_probability (non-NaN): {crisis_probability.dropna().shape[0]} rows")

    engine = WalkForwardHRPEngine(refit_frequency="W", min_train_window=60)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        start = time.perf_counter()
        results = engine.run(asset_returns, crisis_probability)
        elapsed = time.perf_counter() - start

    warning_summary = {}
    for w in caught:
        key = f"{w.category.__name__}: {str(w.message)[:150]}"
        warning_summary[key] = warning_summary.get(key, 0) + 1

    out_path = os.path.join(DATA_DIR, "walk_forward_hrp_real_output.csv")
    results.to_csv(out_path)

    n_refits = int(results["refit"].sum())
    weight_cols = [c for c in results.columns if c.startswith("weight_")]

    print(f"\nRan in {elapsed:.2f}s, {n_refits} refits")
    print(f"Warnings: {sum(warning_summary.values())} total")
    for k, v in warning_summary.items():
        print(f"  {v}x  {k}")

    # --- shrinkage / variance-floor activity across the whole run ---
    fitted_rows = results.dropna(subset=["effective_n_calm"])
    n_calm_shrunk = int(fitted_rows["calm_covariance_shrunk"].sum())
    n_crisis_shrunk = int(fitted_rows["crisis_covariance_shrunk"].sum())
    floored_calm = sorted(set(a for s in fitted_rows["variance_floor_applied_calm"] for a in s.split(",") if a))
    floored_crisis = sorted(set(a for s in fitted_rows["variance_floor_applied_crisis"] for a in s.split(",") if a))

    print("\n=== Safeguard activity (over all daily allocations, not just refits) ===")
    print(f"  calm_covariance_shrunk:   {n_calm_shrunk} / {len(fitted_rows)} days")
    print(f"  crisis_covariance_shrunk: {n_crisis_shrunk} / {len(fitted_rows)} days")
    print(f"  effective_n_crisis range: {fitted_rows['effective_n_crisis'].min():.2f} to {fitted_rows['effective_n_crisis'].max():.2f}")
    print(f"  effective_n_calm range:   {fitted_rows['effective_n_calm'].min():.2f} to {fitted_rows['effective_n_calm'].max():.2f}")
    print(f"  assets ever variance-floored (calm):    {floored_calm}")
    print(f"  assets ever variance-floored (crisis):  {floored_crisis}")

    # per-refit-date detail
    refit_rows = results[results["refit"] == True]
    print("\n=== Per-refit safeguard detail ===")
    print(
        refit_rows[
            [
                "crisis_probability",
                "effective_n_calm",
                "effective_n_crisis",
                "calm_covariance_shrunk",
                "crisis_covariance_shrunk",
                "variance_floor_applied_calm",
                "variance_floor_applied_crisis",
            ]
        ].to_string()
    )

    # --- weights: low-crisis month vs high-crisis month ---
    extra_cols = ["combined_defensive_weight", "defensive_mix_shift"]

    def month_avg(month: str) -> pd.Series:
        sub = results.loc[month, weight_cols + extra_cols]
        return sub.mean()

    low_crisis_month = "2025-06"
    high_crisis_month = "2026-03"

    print(f"\n=== Weights: {low_crisis_month} (low crisis) vs {high_crisis_month} (high crisis) ===")
    low = month_avg(low_crisis_month)
    high = month_avg(high_crisis_month)
    comparison = pd.DataFrame({"low_crisis_avg_weight": low, "high_crisis_avg_weight": high})
    comparison["delta"] = comparison["high_crisis_avg_weight"] - comparison["low_crisis_avg_weight"]
    print(comparison)

    print(f"\navg crisis_probability in {low_crisis_month}: {results.loc[low_crisis_month, 'crisis_probability'].mean():.4f}")
    print(f"avg crisis_probability in {high_crisis_month}: {results.loc[high_crisis_month, 'crisis_probability'].mean():.4f}")

    low_defensive = low["combined_defensive_weight"]
    high_defensive = high["combined_defensive_weight"]
    print(f"\ncombined defensive (bonds+cash) weight: {low_defensive:.4f} (low-crisis month) -> {high_defensive:.4f} (high-crisis month)")
    print(f"defensive_mix_shift (cash / (bonds+cash)): {low['defensive_mix_shift']:.4f} (low-crisis month) -> {high['defensive_mix_shift']:.4f} (high-crisis month)")
    print(f"stocks weight: {low['weight_stocks']:.4f} -> {high['weight_stocks']:.4f}  (expected: pinned near MIN_WEIGHT=0.05 in both)")
    print(f"gold weight:   {low['weight_gold']:.4f} -> {high['weight_gold']:.4f}  (expected: pinned near MIN_WEIGHT=0.05 in both)")

    summary = {
        "elapsed_seconds": round(elapsed, 2),
        "n_refits": n_refits,
        "total_warnings": sum(warning_summary.values()),
        "warning_summary": warning_summary,
        "n_days_calm_shrunk": n_calm_shrunk,
        "n_days_crisis_shrunk": n_crisis_shrunk,
        "n_fitted_days": len(fitted_rows),
        "effective_n_crisis_min": float(fitted_rows["effective_n_crisis"].min()),
        "effective_n_crisis_max": float(fitted_rows["effective_n_crisis"].max()),
        "effective_n_calm_min": float(fitted_rows["effective_n_calm"].min()),
        "effective_n_calm_max": float(fitted_rows["effective_n_calm"].max()),
        "assets_ever_floored_calm": floored_calm,
        "assets_ever_floored_crisis": floored_crisis,
        "low_crisis_month": low_crisis_month,
        "high_crisis_month": high_crisis_month,
        "low_crisis_weights": low.to_dict(),
        "high_crisis_weights": high.to_dict(),
        "defensive_weight_low": float(low_defensive),
        "defensive_weight_high": float(high_defensive),
    }
    with open(os.path.join(DATA_DIR, "walk_forward_hrp_real_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nSaved full output to {out_path}")
    print(f"Saved summary to {os.path.join(DATA_DIR, 'walk_forward_hrp_real_summary.json')}")


if __name__ == "__main__":
    main()
