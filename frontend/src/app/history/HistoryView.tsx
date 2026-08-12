"use client";

import { useMemo, useState } from "react";
import { RegimeHistoryChart } from "@/components/RegimeHistoryChart";
import { MonthlySummaryStrip } from "@/components/MonthlySummaryStrip";
import { TimeRangeTabs } from "@/components/TimeRangeTabs";
import {
  filterByRange,
  findStateCountChanges,
  monthlyAggregate,
  MIN_MONTHLY_BUCKETS,
  type TimeRange,
} from "@/lib/regimeHistory";
import type { RegimeHistoryRow } from "@/lib/api";

export interface HistoryViewProps {
  history: RegimeHistoryRow[];
}

export function HistoryView({ history }: HistoryViewProps) {
  const [range, setRange] = useState<TimeRange>("1Y");
  const filtered = useMemo(() => filterByRange(history, range), [history, range]);
  const stateChanges = useMemo(() => findStateCountChanges(filtered), [filtered]);
  const currentNStates = filtered.at(-1)?.selected_n_states ?? null;
  // Monthly strip is scoped to the SAME range as the main chart above --
  // showing a different window than what's currently selected read as a
  // bug, not a feature (per review). Hidden below MIN_MONTHLY_BUCKETS
  // rather than rendering 1-2 bars that either restate the headline
  // number or average a noisy partial month.
  const monthlyBuckets = useMemo(() => monthlyAggregate(filtered), [filtered]);

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="flex items-baseline justify-between">
          <h1 className="font-kr text-base font-medium text-text">국면 히스토리</h1>
          <span className="font-mono text-[11px] text-muted-2">{filtered.length}일</span>
        </div>

        <TimeRangeTabs value={range} onChange={setRange} className="mt-3" />

        <RegimeHistoryChart history={filtered} className="mt-3" />

        <p className="mt-1 font-kr text-xs text-muted">
          {stateChanges.length === 0 ? (
            <>선택된 상태 수: {currentNStates ?? "-"}개 (선택 기간 내 변경 없음)</>
          ) : (
            <>
              상태 수 변경 {stateChanges.length}회:{" "}
              {stateChanges.map((c) => `${c.date} (${c.from}→${c.to})`).join(", ")}
            </>
          )}
          {" · "}하단 띠는 모델이 구분한 국면 개수(상태 수)를 나타냅니다.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">월별 요약</h2>
        {monthlyBuckets.length >= MIN_MONTHLY_BUCKETS ? (
          <>
            <p className="mt-0.5 font-kr text-xs text-muted">선택한 기간({range}) 기준</p>
            <MonthlySummaryStrip buckets={monthlyBuckets} className="mt-3" />
          </>
        ) : (
          <p className="mt-0.5 font-kr text-xs text-muted">
            선택한 기간이 너무 짧아 월별 요약을 표시할 수 없습니다. 3개월 이상 기간을 선택해
            주세요.
          </p>
        )}
      </section>
    </div>
  );
}
