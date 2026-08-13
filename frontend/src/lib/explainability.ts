import type { AssetKey } from "@/lib/api";

/**
 * Plain-language helpers for the 설명가능성 카드 (explainability card).
 * Translates internal model concepts (canonical low-to-high-variance
 * state ordering, interpolated allocation bounds) into the same
 * 안정/중립/위기 vocabulary already established on the history screen's
 * monthly strip -- one vocabulary for "how risky does this look" across
 * the whole app, not a new one invented per screen.
 */

const ZONE_LABELS_BY_N_STATES: Record<number, string[]> = {
  2: ["안정", "위기"],
  3: ["안정", "중립", "위기"],
};

/** Canonical state order is always low-to-high variance (see
 * filtered_hmm.py's _canonicalize_state_order), so index 0 is always the
 * calmest state regardless of how many states the model selected today. */
export function stateLabel(index: number, nStates: number): string {
  const labels = ZONE_LABELS_BY_N_STATES[nStates];
  if (labels && index < labels.length) return labels[index];
  return `${index + 1}번째 국면`;
}

export interface DeltaDirection {
  direction: "up" | "down" | "flat";
  deltaPoints: number; // percentage points, e.g. +3.2
}

export function computeDelta(current: number, previous: number | null): DeltaDirection | null {
  if (previous === null) return null;
  const deltaPoints = (current - previous) * 100;
  if (Math.abs(deltaPoints) < 0.05) return { direction: "flat", deltaPoints };
  return { direction: deltaPoints > 0 ? "up" : "down", deltaPoints };
}

const ASSET_LABELS_KO: Record<AssetKey, string> = {
  stocks: "주식",
  bonds: "채권",
  cash: "현금",
  gold: "금",
};

export function assetLabel(key: AssetKey): string {
  return ASSET_LABELS_KO[key];
}

export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** "높음/보통/낮음" is a deliberately different word set from
 * lib/regimeHistory.ts's 안정/중립/위기 zoneForProbability -- this tags a
 * raw volatility PERCENTILE (magnitude), not the model's actual regime
 * classification (crisis_probability), and those two can legitimately
 * disagree (a reading can sit at a high raw percentile while the HMM
 * still classifies it well within a calm-leaning regime, since regime
 * boundaries aren't percentile cutoffs). Reusing 안정/중립/위기 for both
 * would make that normal disagreement read as a contradiction. */
export type VolatilityLevel = "낮음" | "보통" | "높음";

export function volatilityLevel(percentile: number): VolatilityLevel {
  if (percentile >= 2 / 3) return "높음";
  if (percentile <= 1 / 3) return "낮음";
  return "보통";
}

/** Percentile is "fraction of days with a LOWER reading than today" --
 * phrased so the number's direction can't be misread (a bare "상위 21%"
 * reads ambiguously positive to a worried reader; explicitly pairing the
 * number with which days it excludes removes that ambiguity). */
export function formatVolatilityContext(percentile: number): string {
  const lowerDaysPct = Math.round(percentile * 100);
  return `최근 약 2년(500거래일) 중 오늘보다 변동성이 낮았던 날이 ${lowerDaysPct}%였습니다`;
}
