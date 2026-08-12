"use client";

import { TIME_RANGES, type TimeRange } from "@/lib/regimeHistory";

export interface TimeRangeTabsProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
  className?: string;
}

export function TimeRangeTabs({ value, onChange, className }: TimeRangeTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="기간 선택"
      className={`flex gap-1 rounded-xl bg-card-2 p-1 ${className ?? ""}`}
    >
      {TIME_RANGES.map((range) => {
        const active = range === value;
        return (
          <button
            key={range}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(range)}
            className={`flex-1 rounded-lg px-2 py-1.5 font-mono text-xs font-medium transition ${
              active ? "bg-card text-text shadow-card" : "text-muted"
            }`}
          >
            {range}
          </button>
        );
      })}
    </div>
  );
}
