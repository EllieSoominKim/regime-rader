"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { AssetKey } from "@/lib/api";

/**
 * Recommended-allocation donut (stocks/bonds/cash/gold), part-to-whole at a
 * glance -- 4 segments is well inside the dataviz skill's "donut is fine
 * for part-to-whole, <=6 segments" allowance (see anti-patterns.md; a
 * donut is flagged there specifically for COMPARING close values, which
 * isn't this component's job).
 *
 * Categorical palette validated with the skill's validator
 * (scripts/validate_palette.js "<hexes>" --mode light --surface "#FFFFFF"
 * --pairs all -> ALL CHECKS PASS) using 4 of its documented default
 * categorical slots (blue/violet/yellow/magenta) -- NOT the app's
 * calm/mid/crisis status tokens, which are reserved for the regime gauge
 * and must never double as series colors (dataviz skill's status-color
 * rule). "gold" is deliberately assigned magenta rather than the palette's
 * yellow slot: yellow (#eda100) measures below the skill's normal-vision
 * separation floor against the app's own --mid amber (#c97f0a) -- both
 * read as "gold-ish orange" side by side, which would be actively
 * misleading here (a large "gold" slice could look like an elevated
 * crisis-mid reading). Yellow went to "cash" instead, which carries no
 * such adjacent status meaning.
 */
const ASSET_COLORS: Record<AssetKey, string> = {
  stocks: "#2a78d6", // categorical slot 1 (blue)
  bonds: "#4a3aa7", // categorical slot 7 (violet)
  cash: "#eda100", // categorical slot 4 (yellow)
  gold: "#e87ba4", // categorical slot 5 (magenta) -- see note above
};

const ASSET_LABELS: Record<AssetKey, string> = {
  stocks: "주식",
  bonds: "채권",
  cash: "현금",
  gold: "금",
};

// Fixed legend/render order -- color follows the entity, never the day's
// ranking, so this order never reshuffles by weight.
const ASSET_ORDER: AssetKey[] = ["stocks", "bonds", "cash", "gold"];

export interface AllocationDonutProps {
  weights: Partial<Record<AssetKey, number>>;
  className?: string;
}

interface DonutDatum {
  key: AssetKey;
  name: string;
  value: number;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: DonutDatum }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-card">
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: ASSET_COLORS[datum.key] }}
        />
        <span className="font-kr text-xs text-muted">{datum.name}</span>
      </div>
      <div className="font-mono text-sm font-bold text-text">
        {(datum.value * 100).toFixed(1)}%
      </div>
    </div>
  );
}

export function AllocationDonut({ weights, className }: AllocationDonutProps) {
  const data: DonutDatum[] = ASSET_ORDER.filter((key) => (weights[key] ?? 0) > 0).map((key) => ({
    key,
    name: ASSET_LABELS[key],
    value: weights[key] ?? 0,
  }));

  return (
    <div className={className}>
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={58}
              outerRadius={86}
              paddingAngle={2}
              cornerRadius={3}
              stroke="var(--card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((datum) => (
                <Cell key={datum.key} fill={ASSET_COLORS[datum.key]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Direct-labeled legend: percentages are read from the numbers, not
          hue alone -- required mitigation for the two segments (cash,
          gold) that sit below 3:1 contrast against the white card. */}
      <ul className="grid grid-cols-2 gap-x-4 gap-y-2 pt-2">
        {data.map((datum) => (
          <li key={datum.key} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: ASSET_COLORS[datum.key] }}
            />
            <span className="font-kr text-sm text-text">{datum.name}</span>
            <span className="ml-auto font-mono text-sm font-medium tabular-nums text-muted">
              {(datum.value * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
