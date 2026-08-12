import type { RegimeHistoryRow } from "@/lib/api";

/**
 * Client-side derivations from GET /api/regime/history's own payload --
 * per scope, no new backend endpoint for the monthly strip or range
 * filtering, both computed from the one history array already fetched.
 */

// ---- time-range tabs ---------------------------------------------------

export type TimeRange = "1M" | "3M" | "1Y" | "전체";
export const TIME_RANGES: TimeRange[] = ["1M", "3M", "1Y", "전체"];

// Trading days, not calendar days (history rows are trading days only).
// The live window checked before building this (499 rows, 2024-07-24 ->
// 2026-08-11, refreshed daily -- see api/pipeline.py's DAYS=500) spans
// ~2 calendar years, so all four tabs slice meaningfully different
// subsets: 1M ~21 rows, 3M ~63, 1Y ~252, 전체 = all 499. If that window
// ever shrinks well under a year, drop the tabs that would stop being
// meaningfully different rather than leaving a decorative one in.
const RANGE_TRADING_DAYS: Record<TimeRange, number> = {
  "1M": 21,
  "3M": 63,
  "1Y": 252,
  전체: Infinity,
};

export function filterByRange(history: RegimeHistoryRow[], range: TimeRange): RegimeHistoryRow[] {
  const n = RANGE_TRADING_DAYS[range];
  return Number.isFinite(n) ? history.slice(-n) : history;
}

// ---- calm/mid/crisis threshold bucketing --------------------------------

export type CrisisZone = "calm" | "mid" | "crisis";

/** Even thirds of the 0-1 probability range -- matches the gauge's own
 * three-stop calm/mid/crisis scale, just discretized for the monthly
 * strip's bar coloring (a bar can't render a continuous gradient
 * legibly at this size the way the gauge's arc can). */
export function zoneForProbability(p: number): CrisisZone {
  if (p < 1 / 3) return "calm";
  if (p < 2 / 3) return "mid";
  return "crisis";
}

// ---- monthly summary strip -----------------------------------------------

export interface MonthlyBucket {
  /** "YYYY-MM" */
  month: string;
  meanProbability: number;
  zone: CrisisZone;
  n: number;
}

/** Below this many distinct months, a "monthly summary strip" isn't a
 * strip -- it's 1-2 bars, which either restates the headline number or
 * (worse) puts a noisy partial-month average next to nothing to compare
 * it against. Checked against the live data while building this: 1M
 * yields 2 months (mostly one real month plus a sliver of the next) --
 * hide; 3M yields 4 -- show; 1Y/전체 yield 14/23 -- clearly show. */
export const MIN_MONTHLY_BUCKETS = 3;

/** Same bucketing convention as
 * data/walk_forward_real_monthly_crisis_probability.csv's own
 * `.resample("MS")` (calendar-month, mean of crisis_probability) --
 * reimplemented client-side here since that CSV is a one-off analysis
 * artifact, not something the API serves. */
export function monthlyAggregate(history: RegimeHistoryRow[]): MonthlyBucket[] {
  const buckets = new Map<string, { sum: number; n: number }>();
  for (const row of history) {
    if (row.crisis_probability === null) continue;
    const month = row.date.slice(0, 7);
    const bucket = buckets.get(month) ?? { sum: 0, n: 0 };
    bucket.sum += row.crisis_probability;
    bucket.n += 1;
    buckets.set(month, bucket);
  }
  return Array.from(buckets.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, { sum, n }]) => {
      const meanProbability = sum / n;
      return { month, meanProbability, zone: zoneForProbability(meanProbability), n };
    });
}

// ---- selected_n_states change detection -----------------------------------

export interface StateCountChange {
  date: string;
  from: number;
  to: number;
}

/** Every date where selected_n_states differs from the prior non-null
 * reading. In the live data checked while building this screen (current
 * rolling 500-day window, refreshed today) this returns an empty array --
 * selected_n_states has been a constant 3 throughout, no change to show.
 * Kept generic so it renders correctly if/when a change does occur. */
export function findStateCountChanges(history: RegimeHistoryRow[]): StateCountChange[] {
  const changes: StateCountChange[] = [];
  let prev: number | null = null;
  for (const row of history) {
    if (row.selected_n_states === null) continue;
    if (prev !== null && row.selected_n_states !== prev) {
      changes.push({ date: row.date, from: prev, to: row.selected_n_states });
    }
    prev = row.selected_n_states;
  }
  return changes;
}
