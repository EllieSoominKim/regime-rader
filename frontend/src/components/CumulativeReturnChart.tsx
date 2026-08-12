"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { findHighCrisisRanges, type EquityPoint } from "@/lib/backtestHistory";

/**
 * Cumulative return, regime-HRP vs 60/40 -- linear scale, deliberately
 * NOT log: the whole point of this screen is not to flatter regime-HRP's
 * much smaller line by rescaling it into a similar-looking shape to
 * 60/40's. The gap looks large because it IS large in this sample (see
 * BacktestMetricsTable's honest takeaway) -- see DrawdownChart directly
 * below for the metric where the comparison reverses.
 *
 * Two plain Lines (not areas) since this is a 2-series comparison, not a
 * single continuous series -- overlapping filled areas would visually
 * obscure each other. Colors are blue (accent, regime-HRP) vs a neutral
 * dark (benchmark), matching BacktestMetricsTable's header treatment --
 * also inherently CVD-safe (blue vs near-black has nothing to do with
 * the red/green confusion axis).
 *
 * Shaded bands mark contiguous high-crisis date ranges, derived from
 * crisis_probability in the data itself (lib/backtestHistory.ts's
 * findHighCrisisRanges) -- never a hardcoded date range.
 */
const REGIME_HRP_COLOR = "var(--accent)";
const BENCHMARK_COLOR = "var(--text)";

function formatDateShort(date: string): string {
  const [, m, d] = date.split("-");
  return `${m}/${d}`;
}

function formatPercent(v: number): string {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

interface TooltipPayloadItem {
  payload: EquityPoint;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-card">
      <div className="font-mono text-[11px] text-muted-2">{datum.date}</div>
      <div className="mt-1 flex items-center gap-1.5">
        <span className="h-1.5 w-3 rounded-full" style={{ backgroundColor: REGIME_HRP_COLOR }} />
        <span className="font-mono text-sm font-bold text-text">
          {formatPercent(datum.regime_hrp_cumulative)}
        </span>
        <span className="font-kr text-[11px] text-muted">Regime-HRP</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-3 rounded-full" style={{ backgroundColor: BENCHMARK_COLOR }} />
        <span className="font-mono text-sm font-bold text-text">
          {formatPercent(datum.benchmark_6040_cumulative)}
        </span>
        <span className="font-kr text-[11px] text-muted">60/40</span>
      </div>
    </div>
  );
}

export interface CumulativeReturnChartProps {
  data: EquityPoint[];
  className?: string;
}

export function CumulativeReturnChart({ data, className }: CumulativeReturnChartProps) {
  const highCrisisRanges = findHighCrisisRanges(data);
  const tickInterval = Math.max(0, Math.ceil(data.length / 6) - 1);

  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: REGIME_HRP_COLOR }} />
          <span className="font-kr text-xs text-muted">Regime-HRP</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: BENCHMARK_COLOR }} />
          <span className="font-kr text-xs text-muted">60/40</span>
        </div>
      </div>

      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />

            {highCrisisRanges.map((range) => (
              <ReferenceArea
                key={range.start}
                x1={range.start}
                x2={range.end}
                fill="var(--crisis)"
                fillOpacity={0.08}
                stroke="none"
              />
            ))}

            <XAxis
              dataKey="date"
              tickFormatter={formatDateShort}
              interval={tickInterval}
              tick={{ fontSize: 10, fontFamily: "var(--font-jetbrains-mono)", fill: "var(--muted-2)" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 10, fontFamily: "var(--font-jetbrains-mono)", fill: "var(--muted-2)" }}
              axisLine={false}
              tickLine={false}
              width={38}
            />

            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--muted-2)", strokeDasharray: "3 3" }} />

            <Line
              type="monotone"
              dataKey="benchmark_6040_cumulative"
              stroke={BENCHMARK_COLOR}
              strokeWidth={1.75}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="regime_hrp_cumulative"
              stroke={REGIME_HRP_COLOR}
              strokeWidth={1.75}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
