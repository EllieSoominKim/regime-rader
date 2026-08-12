import type { BacktestMetrics } from "@/lib/api";

/**
 * Metrics comparison for the 백테스트 비교 screen. Deliberately does NOT
 * color-code a "winner" per row (no green/red cell highlighting) --
 * per FINDINGS.md's real 2025-01-21 -> 2026-08-11 backtest, 60/40 wins
 * total_return, annualized_return, sharpe, AND calmar (a risk-ADJUSTED
 * metric); regime_hrp's only advantage is smaller annualized_vol and mdd
 * (raw risk magnitude, not risk-adjusted return). A per-row winner tag
 * would visually tally as "5-1 for 60/40" and bury the one dimension
 * this product's differentiator actually rests on. Instead: three
 * grouped sections (raw return / risk-adjusted return / raw risk) so the
 * shape of the tradeoff is legible on its own, neutral mono numbers with
 * no color bias, and a magnitude bar ONLY on the raw-risk rows -- where
 * regime_hrp's real advantage is large enough (vol ~14x smaller, mdd
 * ~10x smaller in the reference run) that a length comparison speaks for
 * itself without needing a color verdict.
 */

const PERCENT_FIELDS = ["total_return", "annualized_return", "annualized_vol", "mdd"] as const;
const RATIO_FIELDS = ["sharpe", "calmar"] as const;

function formatMetric(key: string, value: number): string {
  if ((PERCENT_FIELDS as readonly string[]).includes(key)) {
    return `${(value * 100).toFixed(1)}%`;
  }
  if ((RATIO_FIELDS as readonly string[]).includes(key)) {
    return value.toFixed(2);
  }
  return String(value);
}

interface MetricRowSpec {
  key: keyof BacktestMetrics;
  label: string;
  /** Render a magnitude bar comparing |regime_hrp| vs |benchmark_6040| under this row. */
  showBar?: boolean;
}

interface MetricGroup {
  title: string;
  rows: MetricRowSpec[];
}

const GROUPS: MetricGroup[] = [
  {
    title: "수익성",
    rows: [
      { key: "total_return", label: "총수익률" },
      { key: "annualized_return", label: "연환산 수익률" },
    ],
  },
  {
    title: "위험조정 수익",
    rows: [
      { key: "sharpe", label: "샤프비율" },
      { key: "calmar", label: "칼마비율" },
    ],
  },
  {
    title: "위험 (실제 손실 크기)",
    rows: [
      { key: "annualized_vol", label: "연환산 변동성", showBar: true },
      { key: "mdd", label: "최대낙폭 (MDD)", showBar: true },
    ],
  },
];

function MagnitudeBar({
  label,
  value,
  maxAbsValue,
}: {
  label: string;
  value: number;
  maxAbsValue: number;
}) {
  const widthPct = maxAbsValue > 0 ? (Math.abs(value) / maxAbsValue) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 font-mono text-[10px] text-muted-2">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-card-2">
        <div
          className="h-full rounded-full bg-crisis"
          style={{ width: `${Math.max(2, widthPct)}%` }}
        />
      </div>
    </div>
  );
}

export interface BacktestMetricsTableProps {
  regimeHrp: BacktestMetrics;
  benchmark6040: BacktestMetrics;
  className?: string;
}

export function BacktestMetricsTable({ regimeHrp, benchmark6040, className }: BacktestMetricsTableProps) {
  return (
    <div className={className}>
      <div className="grid grid-cols-[1fr,auto,auto] items-center gap-x-3 gap-y-1 pb-1">
        <span />
        <span className="text-right font-mono text-[10px] font-medium uppercase tracking-wide text-accent">
          Regime-HRP
        </span>
        <span className="text-right font-mono text-[10px] font-medium uppercase tracking-wide text-muted">
          60/40
        </span>
      </div>

      {GROUPS.map((group) => (
        <div key={group.title} className="mt-3 first:mt-0">
          <div className="font-kr text-[11px] font-medium text-muted-2">{group.title}</div>
          <div className="mt-1 grid grid-cols-[1fr,auto,auto] items-center gap-x-3 gap-y-2">
            {group.rows.map((row) => {
              const hrpVal = regimeHrp[row.key] as number;
              const benchVal = benchmark6040[row.key] as number;
              return (
                <div key={row.key} className="contents">
                  <span className="font-kr text-sm text-text">{row.label}</span>
                  <span className="text-right font-mono text-sm font-medium tabular-nums text-text">
                    {formatMetric(row.key, hrpVal)}
                  </span>
                  <span className="text-right font-mono text-sm font-medium tabular-nums text-text">
                    {formatMetric(row.key, benchVal)}
                  </span>
                  {row.showBar ? (
                    <div className="col-span-3 flex flex-col gap-1 pb-1 pt-0.5">
                      <MagnitudeBar
                        label="Regime-HRP"
                        value={hrpVal}
                        maxAbsValue={Math.max(Math.abs(hrpVal), Math.abs(benchVal))}
                      />
                      <MagnitudeBar
                        label="60/40"
                        value={benchVal}
                        maxAbsValue={Math.max(Math.abs(hrpVal), Math.abs(benchVal))}
                      />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
