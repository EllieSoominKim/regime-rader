/**
 * Typed client for the regime-rader FastAPI backend (../api/routers/*.py).
 * Types below are transcribed from those routers' actual return shapes
 * (api/pipeline.py's compute_today_snapshot / compute_backtest_summary /
 * compute_synthetic_stress_summary and regime_conditional_hrp.py's
 * WalkForwardHRPEngine row schema), not guessed.
 */

import type { RiskTier } from "@/lib/riskTier";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// ---- shared ----------------------------------------------------------

/** Every endpoint wraps its payload with the same daily-cache envelope
 * (api/cache.py's CacheResult). */
interface CacheEnvelope {
  cache_hit: boolean;
  computed_on: string; // ISO date, e.g. "2026-08-11"
  compute_seconds: number;
}

export type AssetKey = "stocks" | "bonds" | "cash" | "gold";

// ---- GET /api/regime/today --------------------------------------------

export interface RegimeToday extends CacheEnvelope {
  date: string; // ISO date of the underlying data, e.g. "2026-08-10"
  selected_n_states: number;
  selection_criterion: "aic" | "bic";
  crisis_probability: number; // 0-1
  regime: number; // argmax state index under the winning model
  state_probabilities: number[];
  recommended_weights: Partial<Record<AssetKey, number>>;
  combined_defensive_weight: number;
  effective_n_calm: number;
  effective_n_crisis: number;
  calm_covariance_shrunk: boolean;
  crisis_covariance_shrunk: boolean;
  aic_by_candidate: Record<string, number>; // keys are n_states as strings, e.g. "2","3"
  bic_by_candidate: Record<string, number>;
  /** Added for the explainability card -- null only if there's no prior
   * trading day in the fetched window at all (first-ever run). */
  previous_date: string | null;
  previous_crisis_probability: number | null;
  previous_recommended_weights: Partial<Record<AssetKey, number>> | null;
  previous_combined_defensive_weight: number | null;
  /** Raw GARCH-X conditional volatility reading (KTB 3Y yield), not a
   * percentage -- crisis_probability is the derived, interpretable
   * signal; this is the underlying driver behind it. */
  conditional_volatility_today: number;
  /** Fraction (0-1) of days in the fetched window with a LOWER reading
   * than today's -- e.g. 0.79 means today is higher than 79% of the last
   * ~500 trading days. */
  conditional_volatility_percentile: number;
}

// ---- GET /api/regime/history -------------------------------------------

export interface RegimeHistoryRow {
  date: string;
  crisis_probability: number | null;
  selected_n_states: number | null;
  regime: number | null;
  refit: boolean;
}

export interface RegimeHistory extends CacheEnvelope {
  n_rows: number;
  history: RegimeHistoryRow[];
}

// ---- GET /api/hrp/history ------------------------------------------------

export interface HrpHistoryRow {
  date: string;
  refit: boolean;
  crisis_probability: number | null;
  weight_stocks: number | null;
  weight_bonds: number | null;
  weight_cash: number | null;
  weight_gold: number | null;
  effective_n_calm: number | null;
  effective_n_crisis: number | null;
  calm_covariance_shrunk: boolean | null;
  crisis_covariance_shrunk: boolean | null;
  variance_floor_applied_calm: string; // comma-joined asset names, "" if none
  variance_floor_applied_crisis: string;
  combined_defensive_weight: number | null;
  defensive_mix_shift: number | null; // cash / (bonds + cash)
}

export interface HrpHistory extends CacheEnvelope {
  n_rows: number;
  history: HrpHistoryRow[];
}

// ---- GET /api/backtest/summary -------------------------------------------

export interface BacktestMetrics {
  n_days: number;
  total_return: number;
  annualized_return: number;
  annualized_vol: number;
  sharpe: number;
  mdd: number;
  calmar: number;
}

export interface BacktestWindow {
  regime_hrp: BacktestMetrics;
  benchmark_6040: BacktestMetrics;
}

export interface BacktestDailyReturn {
  date: string;
  regime_hrp: number;
  benchmark_6040: number;
  /** From hrp_history's own column, aligned to this row's date -- lets
   * the frontend derive "high-crisis" date ranges from the data itself
   * (see lib/backtestHistory.ts's findHighCrisisRanges) instead of a
   * hardcoded HIGH_CRISIS_START/END literal, which would go stale the
   * next time this backtest re-runs on a shifted window. */
  crisis_probability: number | null;
}

export interface RealBacktestSummary {
  window_start: string;
  window_end: string;
  n_days: number;
  risk_free_annual: number;
  full_window: BacktestWindow;
  /** keys like "regime_hrp__high_crisis_feb_jun_2026", "benchmark_6040__rest_of_window" */
  regime_split: Record<string, BacktestMetrics>;
  daily_returns: BacktestDailyReturn[];
  assumptions: {
    benchmark_weights: Partial<Record<AssetKey, number>>;
    benchmark_rebalance: string;
    regime_hrp_rebalance: string;
    transaction_costs: string;
    risk_free_source: string;
  };
}

export interface SyntheticStressSummary {
  label: string; // always flagged "SYNTHETIC STRESS TEST -- NOT REAL HISTORICAL DATA"
  crash_start: string;
  crash_n_days: number;
  crash_total_return_target: number;
  window_start: string;
  window_end: string;
  risk_free_annual: number;
  full_window: BacktestWindow;
  /** keys like "regime_hrp__crash_window_25d", "benchmark_6040__high_crisis_feb_jun_2026" */
  regime_split: Record<string, BacktestMetrics>;
}

export interface BacktestSummary extends CacheEnvelope {
  real_backtest: RealBacktestSummary;
  synthetic_stress_test: SyntheticStressSummary;
}

// ---- fetch wrapper ---------------------------------------------------

async function apiFetch<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  } catch (cause) {
    throw new Error(
      `regime-rader API unreachable at ${API_BASE_URL}${path} -- is the FastAPI server running? (uvicorn api.main:app --port 8000)`,
      { cause },
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} -> HTTP ${res.status}: ${body.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

/** riskTier is optional only for callers that genuinely don't care (e.g. a
 * future admin/debug view) -- both app pages that call this pass the
 * request-scoped tier resolved from the URL (see lib/riskTier.ts's
 * parseRiskTier + components/RiskTierSync.tsx), never the bare default,
 * so a user's onboarding choice actually reaches the backend's cache-keyed
 * /api/regime/today (see api/routers/regime.py). */
export function getRegimeToday(riskTier?: RiskTier): Promise<RegimeToday> {
  const query = riskTier ? `?risk_tier=${encodeURIComponent(riskTier)}` : "";
  return apiFetch<RegimeToday>(`/api/regime/today${query}`);
}

export function getRegimeHistory(): Promise<RegimeHistory> {
  return apiFetch<RegimeHistory>("/api/regime/history");
}

export function getHrpHistory(): Promise<HrpHistory> {
  return apiFetch<HrpHistory>("/api/hrp/history");
}

export function getBacktestSummary(): Promise<BacktestSummary> {
  return apiFetch<BacktestSummary>("/api/backtest/summary");
}
