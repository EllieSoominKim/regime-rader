"use client";

import type { CrisisZone, MonthlyBucket } from "@/lib/regimeHistory";

const ZONE_COLOR: Record<CrisisZone, string> = {
  calm: "var(--calm)",
  mid: "var(--mid)",
  crisis: "var(--crisis)",
};

const ZONE_LABEL: Record<CrisisZone, string> = {
  calm: "안정",
  mid: "중립",
  crisis: "위기",
};

const ZONE_ORDER: CrisisZone[] = ["calm", "mid", "crisis"];
const BAR_MAX_HEIGHT = 44; // px
const LABEL_EVERY_N = 3; // avoid crowding ~25 monthly ticks on a mobile card

function formatMonthLabel(month: string): string {
  const [y, m] = month.split("-");
  return `${y.slice(2)}.${m}`;
}

export interface MonthlySummaryStripProps {
  /** Pre-aggregated by the caller (lib/regimeHistory.ts's monthlyAggregate)
   * from whatever slice of history is currently active -- see
   * HistoryView, which scopes this to the same 1M/3M/1Y/전체 tab as the
   * main chart rather than always showing the full history, and hides
   * this component entirely below MIN_MONTHLY_BUCKETS. */
  buckets: MonthlyBucket[];
  className?: string;
}

/**
 * Monthly mean crisis_probability, bucketed into calm/mid/crisis thirds
 * (see lib/regimeHistory.ts's zoneForProbability) and colored accordingly
 * -- derived entirely client-side from the same /api/regime/history
 * payload the main chart uses, same bucketing convention as
 * data/walk_forward_real_monthly_crisis_probability.csv's `.resample("MS")`.
 */
export function MonthlySummaryStrip({ buckets, className }: MonthlySummaryStripProps) {
  return (
    <div className={className}>
      <div className="flex items-center gap-3 pb-2">
        {ZONE_ORDER.map((zone) => (
          <div key={zone} className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: ZONE_COLOR[zone] }} />
            <span className="font-kr text-[11px] text-muted">{ZONE_LABEL[zone]}</span>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <div className="flex items-end gap-1" style={{ height: BAR_MAX_HEIGHT }}>
          {buckets.map((bucket) => (
            <div
              key={bucket.month}
              className="w-4 shrink-0 rounded-sm"
              style={{
                height: Math.max(3, bucket.meanProbability * BAR_MAX_HEIGHT),
                backgroundColor: ZONE_COLOR[bucket.zone],
              }}
              title={`${bucket.month}: ${(bucket.meanProbability * 100).toFixed(1)}%`}
            />
          ))}
        </div>
        <div className="mt-1 flex gap-1">
          {buckets.map((bucket, i) => (
            <div key={bucket.month} className="w-4 shrink-0 text-center">
              <span className="font-mono text-[8px] text-muted-2">
                {i % LABEL_EVERY_N === 0 ? formatMonthLabel(bucket.month) : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
