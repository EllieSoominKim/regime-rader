"use client";

/**
 * Signature semicircle radar gauge: calm -> mid -> crisis arc with a needle
 * pointing at the current crisis_probability, large mono percentage in the
 * center. Reusable / driven entirely by the `crisisProbability` prop (0-1)
 * so it can be reused wherever a regime read needs to render (history
 * scrubber, explainability card, ...), not just the Home screen.
 *
 * The calm->mid->crisis sweep is a continuous status GRADIENT, not a
 * categorical series -- it's the exact three-stop scale the design tokens
 * name (--calm/--mid/--crisis), so this deliberately does not go through
 * the dataviz skill's categorical-palette validator (that governs discrete
 * series identity, e.g. AllocationDonut's asset colors -- see that
 * component for where the validator actually applies).
 */

const SIZE = 240; // viewBox width
const CX = SIZE / 2;
const CY = 132;
const RADIUS = 96;
const STROKE_WIDTH = 20;
const NEEDLE_LENGTH = RADIUS - STROKE_WIDTH - 6;

function clamp01(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}

/** p=0 -> needle points left (180deg), p=1 -> needle points right (0deg). */
function angleForProbability(p: number): number {
  return Math.PI - clamp01(p) * Math.PI;
}

function pointOnArc(radius: number, angleRad: number): { x: number; y: number } {
  return {
    x: CX + radius * Math.cos(angleRad),
    y: CY - radius * Math.sin(angleRad),
  };
}

export interface RadarGaugeProps {
  /** Crisis probability, 0-1. */
  crisisProbability: number;
  /** Optional label under the percentage, e.g. a regime name. */
  caption?: string;
  className?: string;
}

export function RadarGauge({ crisisProbability, caption, className }: RadarGaugeProps) {
  const p = clamp01(crisisProbability);
  const arcStart = pointOnArc(RADIUS, Math.PI);
  const arcEnd = pointOnArc(RADIUS, 0);
  const needleAngle = angleForProbability(p);
  const needleTip = pointOnArc(NEEDLE_LENGTH, needleAngle);
  const percentLabel = `${(p * 100).toFixed(1)}%`;
  const gradientId = "radar-gauge-gradient";

  return (
    <div className={className}>
      <svg
        viewBox={`0 0 ${SIZE} ${CY + 24}`}
        role="img"
        aria-label={`위기 확률 ${percentLabel}`}
        className="w-full"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--calm)" />
            <stop offset="50%" stopColor="var(--mid)" />
            <stop offset="100%" stopColor="var(--crisis)" />
          </linearGradient>
        </defs>

        {/* Arc track */}
        <path
          d={`M ${arcStart.x} ${arcStart.y} A ${RADIUS} ${RADIUS} 0 0 1 ${arcEnd.x} ${arcEnd.y}`}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
        />

        {/* End labels */}
        <text
          x={arcStart.x}
          y={CY + 20}
          textAnchor="start"
          className="fill-muted font-mono text-[10px] font-medium uppercase tracking-[0.15em]"
        >
          Calm
        </text>
        <text
          x={arcEnd.x}
          y={CY + 20}
          textAnchor="end"
          className="fill-muted font-mono text-[10px] font-medium uppercase tracking-[0.15em]"
        >
          Crisis
        </text>

        {/* Needle */}
        <line
          x1={CX}
          y1={CY}
          x2={needleTip.x}
          y2={needleTip.y}
          stroke="var(--text)"
          strokeWidth={3}
          strokeLinecap="round"
        />
        <circle cx={CX} cy={CY} r={7} fill="var(--text)" />

        {/* Center readout */}
        <text
          x={CX}
          y={CY - 24}
          textAnchor="middle"
          className="fill-text font-mono text-[34px] font-bold"
        >
          {percentLabel}
        </text>
        {caption ? (
          <text
            x={CX}
            y={CY - 2}
            textAnchor="middle"
            className="fill-muted font-kr text-[12px] font-medium"
          >
            {caption}
          </text>
        ) : null}
      </svg>
    </div>
  );
}
