/**
 * Fixed, full-viewport concentric-ring texture behind all page content --
 * the "radar board" backdrop referenced in the mockup: "very low-opacity
 * accent-colored circles". Purely decorative (aria-hidden,
 * pointer-events-none) so it never competes with real data ink -- strokes
 * use --accent at low opacity (not a solid tint), which is what keeps this
 * a texture rather than a chart element competing for attention.
 */
const RING_COUNT = 7;
const RING_STEP = 130; // px between concentric rings
const CENTER_X = "78%"; // upper-right-of-center, echoing the small radar mark in the header
const CENTER_Y = -80; // px, just above the viewport so rings sweep down into the page

export function RadarBackground() {
  const rings = Array.from({ length: RING_COUNT }, (_, i) => (i + 1) * RING_STEP);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      <svg className="h-full w-full" preserveAspectRatio="xMidYMid slice">
        {rings.map((r) => (
          <circle
            key={r}
            cx={CENTER_X}
            cy={CENTER_Y}
            r={r}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={1}
            opacity={0.08}
          />
        ))}
      </svg>
    </div>
  );
}
