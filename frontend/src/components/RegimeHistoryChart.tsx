"use client";

import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RegimeHistoryRow } from "@/lib/api";

/**
 * Primary content of the 국면 히스토리 screen: crisis_probability as an
 * area chart (per the dataviz skill's choosing-a-form -- change over time,
 * one continuous series -> area/line, no legend needed for a single
 * series) with selected_n_states folded into the SAME chart as a thin bar
 * strip pinned to the bottom via a second, near-zero-domain y-axis -- not
 * a separate chart component, so it stays visually read as context for
 * the line above rather than a second insight competing for attention.
 *
 * CVD check on the calm->mid->crisis fill (ran the dataviz skill's
 * validator on the three stops, `--pairs all` and `--ordinal`):
 *   - adjacent/all-pairs: mid<->crisis FAILS both CVD separation (deutan
 *     ΔE 5.8, below even the 6.0 floor) and the normal-vision floor
 *     (13.6, below 15) -- amber and red are genuinely hard to tell apart
 *     here, worse under deuteranopia, confirming the review concern.
 *   - --ordinal: FAILS lightness monotonicity (L goes
 *     0.637 calm -> 0.659 mid -> 0.599 crisis, mid is actually the
 *     LIGHTEST stop, not a step between the other two) and hue-spread
 *     (137°, nowhere near a single-hue ramp).
 *   These FAILs are not fixable by re-choosing hexes without violating
 *   "use these tokens exactly" -- a calm/mid/crisis traffic-light ramp is
 *   inherently a 3-hue semantic scale, not the skill's single-hue
 *   sequential ideal, and swapping the token values was out of scope.
 *   Mitigation actually shipped, addressing the substance of the
 *   concern without touching the tokens:
 *   (1) stop-opacity on the SAME gradient (25% at the calm end -> 85% at
 *       the crisis end) layers a genuine LUMINANCE ramp under the hue
 *       ramp. Alpha-blending toward the white card is a linear operation
 *       independent of hue, so this lightness trend survives protan/
 *       deutan simulation intact even where the hue itself degrades --
 *       unlike the hue channel, this is exactly the channel CVD does NOT
 *       impair.
 *   (2) Two dashed ReferenceLines at the 33%/66% zone boundaries give a
 *       structural, position-based cue for exactly where "mid" ends and
 *       "crisis" begins, independent of color entirely.
 *   (3) The actual data-bearing mark -- the stroke line itself -- is a
 *       flat neutral (--text), never part of the hue ramp, so the
 *       precise value is always readable via line-height-against-axis
 *       regardless of any of the above.
 *
 * State-count band color: n_states is an ORDINAL magnitude (how many
 * regimes the model is currently distinguishing), not a category identity,
 * so it's encoded as one hue (--accent) at two opacity steps -- a
 * light-to-dark sequential ramp, matching the dataviz skill's sequential
 * rule ("one hue, light->dark") rather than treated as a 2-color
 * categorical pair.
 */

const GRADIENT_ID = "regime-history-gradient";

interface ChartDatum {
  date: string;
  crisis_probability: number;
  selected_n_states: number;
  stateBand: 1;
}

function toChartData(history: RegimeHistoryRow[]): ChartDatum[] {
  return history
    .filter(
      (row): row is RegimeHistoryRow & { crisis_probability: number; selected_n_states: number } =>
        row.crisis_probability !== null && row.selected_n_states !== null,
    )
    .map((row) => ({
      date: row.date,
      crisis_probability: row.crisis_probability,
      selected_n_states: row.selected_n_states,
      stateBand: 1,
    }));
}

/** Light->dark single-hue (--accent) sequential step for the ordinal
 * n_states band. Anchored at candidate_state_counts' actual base (2, see
 * api/pipeline.py's WALK_FORWARD_CONFIG) rather than an arbitrary 2-4
 * clamp -- a generic clamp put most of its contrast range on a 4-state
 * case that never occurs, leaving the real 2-vs-3 case (0.3 vs 0.55
 * opacity, a ~48/255 RGB-channel gap over the white card) uncomfortably
 * close for a 2px band, per the mobile-brightness gut-check. This
 * version gives the real case a ~0.35 opacity step (~69/255 gap)
 * instead, still scaling (clamped at 0.95) if a higher state count is
 * ever selected. */
function stateBandOpacity(nStates: number): number {
  const BASE_N_STATES = 2;
  const OPACITY_AT_BASE = 0.28;
  const OPACITY_STEP = 0.35;
  const stepsAboveBase = Math.max(0, nStates - BASE_N_STATES);
  return Math.min(0.95, OPACITY_AT_BASE + stepsAboveBase * OPACITY_STEP);
}

function formatDateShort(date: string): string {
  const [, m, d] = date.split("-");
  return `${m}/${d}`;
}

interface TooltipPayloadItem {
  payload: ChartDatum;
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const datum = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-card">
      <div className="font-mono text-[11px] text-muted-2">{datum.date}</div>
      <div className="font-mono text-lg font-bold text-text">
        {(datum.crisis_probability * 100).toFixed(1)}%
      </div>
      <div className="font-kr text-xs text-muted">상태 수: {datum.selected_n_states}개</div>
    </div>
  );
}

export interface RegimeHistoryChartProps {
  history: RegimeHistoryRow[];
  className?: string;
}

export function RegimeHistoryChart({ history, className }: RegimeHistoryChartProps) {
  const data = toChartData(history);
  const tickInterval = Math.max(0, Math.ceil(data.length / 6) - 1);

  return (
    <div className={className}>
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
            barCategoryGap={0}
            barGap={0}
          >
            <defs>
              <linearGradient id={GRADIENT_ID} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--crisis)" stopOpacity={0.85} />
                <stop offset="50%" stopColor="var(--mid)" stopOpacity={0.55} />
                <stop offset="100%" stopColor="var(--calm)" stopOpacity={0.25} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />

            <XAxis
              dataKey="date"
              tickFormatter={formatDateShort}
              interval={tickInterval}
              tick={{ fontSize: 10, fontFamily: "var(--font-jetbrains-mono)", fill: "var(--muted-2)" }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />

            {/* Primary axis: crisis_probability, 0-1. */}
            <YAxis
              yAxisId="probability"
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 10, fontFamily: "var(--font-jetbrains-mono)", fill: "var(--muted-2)" }}
              axisLine={false}
              tickLine={false}
              width={34}
            />

            {/* Secondary axis: purely to pin the state-count band to a
                thin sliver at the bottom of the SAME plot area -- domain
                max of 8 against a constant bar value of 1 renders each
                bar at ~1/8 of the chart's height. */}
            <YAxis yAxisId="stateband" domain={[0, 8]} hide />

            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--muted-2)", strokeDasharray: "3 3" }} />

            {/* Structural, hue-independent zone boundaries -- see the CVD
                note above. */}
            <ReferenceLine
              yAxisId="probability"
              y={1 / 3}
              stroke="var(--muted-2)"
              strokeDasharray="2 3"
              strokeWidth={1}
            />
            <ReferenceLine
              yAxisId="probability"
              y={2 / 3}
              stroke="var(--muted-2)"
              strokeDasharray="2 3"
              strokeWidth={1}
            />

            <Area
              yAxisId="probability"
              type="monotone"
              dataKey="crisis_probability"
              stroke="var(--text)"
              strokeWidth={1.75}
              fill={`url(#${GRADIENT_ID})`}
              isAnimationActive={false}
            />

            <Bar yAxisId="stateband" dataKey="stateBand" isAnimationActive={false}>
              {data.map((datum) => (
                <Cell
                  key={datum.date}
                  fill="var(--accent)"
                  fillOpacity={stateBandOpacity(datum.selected_n_states)}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
