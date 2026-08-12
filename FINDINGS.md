# Findings log

Running notes on empirical findings worth remembering for the competition
writeup and the week-3 explainability card — written down while fresh
rather than reconstructed from git log later. Newest entries at the top.
Each entry links the commit(s)/script(s) that produced it so the number
can be regenerated, not just cited.

---

## 2026-08-10 — MIN_WEIGHT-pinning bug: the regime mechanism was invisible in final weights

**Finding:** `RegimeConditionalHRP`'s growth-asset floor (`MIN_WEIGHT`) was
a single fixed 0.05 applied to stocks/gold in every regime. Raw
(unbounded) risk-parity weights for those assets in our 4-asset universe
are ~0.1–0.3% in both calm and crisis (stocks/gold variance is ~200–250x
bonds/cash's, even after the variance floor), so the fixed 0.05 floor was
*always* the binding constraint — confirmed by measuring `weight_stocks`
at exactly 0.05 to machine precision on both a calm day (2025-06) and a
synthetic crash day (2026-03/04). The crisis-covariance blending and
defensive-cap widening were computing correctly underneath but never
showed up in the actual output weights at all. This directly contradicted
the design doc's core differentiator ("정적 글라이드패스가 아닌 국면 인식
기반 동적 조정" — dynamic regime-aware adjustment, not a static glidepath).

**Fix:** interpolate the growth floor by `crisis_probability`, symmetric
to the existing defensive-cap widening: `CALM_GROWTH_MIN_WEIGHT=0.05`,
`CRISIS_GROWTH_MIN_WEIGHT=0.0` (deliberately all the way to 0 — any small
positive floor still binds given the observed raw weights). Verified the
mechanism is now genuinely dynamic day-by-day, not just differently
pinned: `weight_stocks` drops from ~5% in calm conditions to ~0.2% during
the synthetic crash's actual trading days.

**Where:** `regime_conditional_hrp.py` (`CALM_GROWTH_MIN_WEIGHT` /
`CRISIS_GROWTH_MIN_WEIGHT`), commit `3d445a4`. Regression test:
`tests/test_regime_conditional_hrp.py::test_growth_asset_floor_is_regime_responsive_not_pinned`.

**For the explainability card:** if it ever surfaces "why is my growth
allocation so low," the honest answer is two-layered — (1) this asset
universe's variance gap means risk-parity wants very little equity/gold
even at baseline, by design (MIN_WEIGHT sets the calm-period floor at 5%,
not 0%), and (2) that floor legitimately drops further as
`crisis_probability` rises. Both are intentional, not bugs.

---

## 2026-08-10 — Real 378-day backtest: honest result is mixed, not a clean win

**Finding:** Backtested `WalkForwardHRPEngine`'s actual daily weights
against a static 60/40 (stocks/bonds only, monthly-rebalanced) benchmark
over the real 2025-01-17 → 2026-08-07 window (378 days), risk-free rate =
the `cash` column's own annualized yield.

| | total return | ann. return | ann. vol | Sharpe | MDD | Calmar |
|---|---|---|---|---|---|---|
| regime_hrp | 4.6% | 3.0% | 1.8% | 0.17 | **-2.11%** | 1.43 |
| benchmark_6040 | **78.3%** | **47.0%** | 26.0% | **1.71** | -23.9% | **1.97** |

**60/40 wins decisively on return and Sharpe, everywhere, including during
the flagged crisis period. Regime-HRP wins decisively on drawdown (MDD
~10x smaller).** Not a clean "regime-HRP works" or "regime-HRP fails"
story — it's a real risk/return tradeoff that, on this specific window,
did not pay off in Sharpe terms. State this plainly in the writeup, not a
metric chosen after the fact to look favorable.

**Where:** `data/backtest_regime_hrp_vs_6040.py`, output in
`data/backtest_summary.json`, commit `1d3c721`.

**Caveat to repeat every time this number is cited:** 378 days containing
exactly one flagged crisis episode (Feb–Jun 2026) is a thin sample. This
result should not be read as "regime-HRP doesn't work" any more than it
should be read as "regime-HRP works" — see the next two entries for why.

---

## 2026-08-10 — Signal-decoupling: rate-vol crisis ≠ equity stress, in this sample

**Finding:** The regime signal (`crisis_probability`) is derived purely
from 3Y KTB yield volatility (via GARCH-X + HMM) — it has no equity
information in it at all. In the real 500-day window, the flagged
high-crisis period (Feb–Jun 2026, `crisis_probability` sustained
0.92–0.98) **coincided with a KOSPI bull run, not a selloff** —
`benchmark_6040` returned +119% annualized *during* the flagged crisis
window. So a system that correctly deepens its defensive tilt when the
crisis flag is high ends up deepening it during a rally in this sample,
not ahead of a crash — which is exactly why the real backtest's Sharpe
looks bad despite the mechanism working as designed.

This is a **signal-relevance limitation**, not an implementation bug: a
rate-volatility-only regime signal doesn't reliably predict equity stress
specifically. It was *hidden* before the MIN_WEIGHT fix (mechanism was
inert, so it couldn't hurt or help) and became *visible* in the P&L only
once the mechanism could actually act on the signal.

**For the writeup:** frame this as the single most important limitation
of the current design, and the natural next research question — does
adding a second observation variable more directly tied to equity/market
stress (see the 환율/FX idea below) fix it, or is rate-vol simply the
wrong primary signal for an equity-heavy allocation decision?

**Where:** established via `data/run_walk_forward_real_ktb.py`'s monthly
`crisis_probability` output crossed against `data/asset_returns.csv`'s
`stocks` column; made P&L-visible via `data/backtest_regime_hrp_vs_6040.py`
after commit `3d445a4`.

---

## 2026-08-10 — Synthetic stress test: the mechanism DOES protect when signal and stress coincide

**Finding:** Spliced a synthetic, precisely-calibrated -20% equity decline
over 25 trading days into the real data, timed inside the real Feb–Jun
2026 rate-vol crisis window (bonds/gold/cash and `crisis_probability`
left untouched — the crisis signal never depended on equity data, so it
doesn't need re-deriving). Re-ran the full walk-forward mechanism
(refitting `RegimeConditionalHRP` on the spliced history) and re-backtested.

| (25-day crash window) | total return | MDD |
|---|---|---|
| regime_hrp | **-0.41%** | **-0.43%** |
| benchmark_6040 | -12.57% | -12.24% |

When a real equity crash *does* coincide with the flagged regime, regime-HRP
cuts the loss by roughly 30x and the drawdown by roughly 28x relative to
the static benchmark. Verified this is the mechanism actually reacting
(not a coincidence of an already-low floor): `weight_stocks` measured
day-by-day drops from ~5% pre-fix-baseline down to ~0.17–0.21% specifically
during the crash days, post the MIN_WEIGHT fix.

**This is the mechanism-level validation the real 500-day sample couldn't
provide on its own** (see the entry above) — it directly answers "does the
defensive tilt actually protect against a drawdown when one coincides with
the flagged regime," independent of whether that coincidence happened to
occur in the one real crisis episode available.

**Where:** `data/backtest_synthetic_crash_stress_test.py`, output in
`data/synthetic_stress_test_summary.json`, commit `1d3c721`. Clearly
labeled synthetic in all outputs — not to be cited as real historical
performance.

**[2026-08-12 correction]** The MDD figures above (-0.43%/-12.24%, "~28x")
were computed with a `compute_metrics` bug: its running-max calculation
didn't seed the peak at the starting capital (1.0), so a day-1 loss
within a sliced sub-window could go uncounted. Fixed in
`data/backtest_regime_hrp_vs_6040.py` / `data/backtest_synthetic_crash_stress_test.py`.
Corrected MDD: regime_hrp -0.62%, benchmark_6040 -12.57%, ratio ~20.3x.
Every other number in this file was checked against the fix directly
and is unaffected (audited all 16 `compute_metrics` call sites — full
window, `high_crisis_feb_jun_2026`, `rest_of_window`, and this
`crash_window_25d` slice — across both the real and synthetic backtests,
on both the frozen historical data and fresh live data; this
`crash_window_25d` slice was the only one where the bug actually changed
a number). `total_return` is untouched — it never depended on this
logic — so the "cuts the loss ~30x" total-return claim above still
stands; only the MDD figures and the "~28x" drawdown-ratio claim moved.
`data/synthetic_stress_test_summary.json` has been regenerated with the
fix; the pre-fix version is archived at
`data/archive/synthetic_stress_test_summary_2026-08-11_prefix-bug.json`.

---

## Open items for later (not started, or explicitly deferred)

- **환율 (FX) as a second HMM observation variable**, per the design doc's
  mentioned extension — flagged by the user as worth a quick (~30 min)
  ECOS feasibility check before committing time to it, specifically
  because FX often moves with equity stress more than domestic rate vol
  does, which is exactly the gap the signal-decoupling finding above
  identifies. Not yet checked.
- **Cash-return realism**: `data/fetch_asset_returns.py`'s cash return is
  a pure yield-accrual (`yield/100/252`) with zero price-change noise,
  almost certainly understating real MMF/CD-linked NAV volatility more
  than the bonds duration-approximation understates bond risk. Flagged as
  a legitimate post-deadline improvement, not urgent for Sept 7 (see the
  variance-gap sanity check earlier in the session).
- **Gold's two distinct data-quality caveats** (documented in
  `RegimeConditionalHRP`'s docstring): flat-day correlation dilution
  (474/498 days are forward-fill-flat) and crisis-split timing
  misalignment (the one real print per month lands on an arbitrary day
  relative to that month's crisis_probability path) — both should be
  called out again if/when gold's correlation figures feed the dashboard.
