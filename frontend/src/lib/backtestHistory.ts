import { zoneForProbability } from "@/lib/regimeHistory";
import type { BacktestDailyReturn } from "@/lib/api";

/**
 * Client-side derivations from /api/backtest/summary's daily_returns
 * array: compounds daily simple returns into a cumulative equity curve,
 * and separately into a running drawdown-from-peak series for the
 * underwater chart. Both charts read directly from this, so they always
 * agree with each other and with the metrics table (same source data).
 */

export interface EquityPoint {
  date: string;
  regime_hrp_cumulative: number; // e.g. 0.05 = +5% since window start
  benchmark_6040_cumulative: number;
  regime_hrp_drawdown: number; // <= 0, e.g. -0.02 = 2% below running peak
  benchmark_6040_drawdown: number;
  crisis_probability: number | null;
}

export function buildEquityCurve(daily: BacktestDailyReturn[]): EquityPoint[] {
  let hrpEquity = 1;
  let benchEquity = 1;
  let hrpPeak = 1;
  let benchPeak = 1;

  return daily.map((row) => {
    hrpEquity *= 1 + row.regime_hrp;
    benchEquity *= 1 + row.benchmark_6040;
    hrpPeak = Math.max(hrpPeak, hrpEquity);
    benchPeak = Math.max(benchPeak, benchEquity);

    return {
      date: row.date,
      regime_hrp_cumulative: hrpEquity - 1,
      benchmark_6040_cumulative: benchEquity - 1,
      regime_hrp_drawdown: hrpEquity / hrpPeak - 1,
      benchmark_6040_drawdown: benchEquity / benchPeak - 1,
      crisis_probability: row.crisis_probability,
    };
  });
}

export interface DateRange {
  start: string;
  end: string;
}

/**
 * Contiguous date ranges where crisis_probability sits in the "crisis"
 * third -- SAME threshold as lib/regimeHistory.ts's zoneForProbability
 * (the one already used for the history screen's monthly strip), reused
 * here rather than inventing a second definition of "high crisis". This
 * is what lets both charts shade the actual flagged window from the
 * data on every load, instead of a hardcoded date literal that would
 * silently go stale once this backtest re-runs on a shifted window.
 */
export function findHighCrisisRanges(points: EquityPoint[]): DateRange[] {
  const ranges: DateRange[] = [];
  let start: string | null = null;
  let prevDate: string | null = null;

  for (const point of points) {
    const isCrisis =
      point.crisis_probability !== null && zoneForProbability(point.crisis_probability) === "crisis";

    if (isCrisis && start === null) {
      start = point.date;
    } else if (!isCrisis && start !== null) {
      ranges.push({ start, end: prevDate ?? start });
      start = null;
    }
    prevDate = point.date;
  }
  if (start !== null && prevDate !== null) {
    ranges.push({ start, end: prevDate });
  }
  return ranges;
}
