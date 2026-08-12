"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { findHighCrisisRanges, type EquityPoint } from "@/lib/backtestHistory";

/**
 * "Underwater" chart -- running drawdown from each strategy's own peak,
 * same x-axis and shaded high-crisis bands as CumulativeReturnChart
 * directly above it. This is where the comparison reverses: regime-HRP's
 * fill barely leaves the 0% line while 60/40's goes deep, the same story
 * BacktestMetricsTable's magnitude bars tell as numbers -- this is that
 * same fact shown as a shape over time.
 *
 * Same color convention as CumulativeReturnChart (accent = regime-HRP,
 * neutral dark = 60/40). 60/40's (much larger) area is drawn first so
 * regime-HRP's (much smaller) area renders on top and stays visible
 * rather than being completely covered.
 */
const REGIME_HRP_COLOR = "var(--accent)";
const BENCHMARK_COLOR = "var(--text)";

function formatDateShort(date: string): string {
  const [, m, d] = date.split("-");
  return `${m}/${d}`;
}

function formatPercent(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
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
        <span className="font-mono text-sm font-bold text-text">{formatPercent(datum.regime_hrp_drawdown)}</span>
        <span className="font-kr text-[11px] text-muted">Regime-HRP</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="h-1.5 w-3 rounded-full" style={{ backgroundColor: BENCHMARK_COLOR }} />
        <span className="font-mono text-sm font-bold text-text">{formatPercent(datum.benchmark_6040_drawdown)}</span>
        <span className="font-kr text-[11px] text-muted">60/40</span>
      </div>
    </div>
  );
}

export interface DrawdownChartProps {
  data: EquityPoint[];
  className?: string;
}

export function DrawdownChart({ data, className }: DrawdownChartProps) {
  const highCrisisRanges = findHighCrisisRanges(data);
  const tickInterval = Math.max(0, Math.ceil(data.length / 6) - 1);

  return (
    <div className={className}>
      <div className="h-[140px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
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

            <Area
              type="monotone"
              dataKey="benchmark_6040_drawdown"
              stroke={BENCHMARK_COLOR}
              strokeWidth={1.25}
              fill={BENCHMARK_COLOR}
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="regime_hrp_drawdown"
              stroke={REGIME_HRP_COLOR}
              strokeWidth={1.25}
              fill={REGIME_HRP_COLOR}
              fillOpacity={0.35}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
