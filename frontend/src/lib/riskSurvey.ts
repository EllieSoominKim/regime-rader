import type { RiskTier } from "@/lib/riskTier";

/**
 * Onboarding risk-tolerance survey: 3 questions, additive point scoring,
 * mapped to a RiskTier. Scoring design approved 2026-08-13 (see
 * conversation/commit history around the risk-tier feature) -- the
 * specific point values and thresholds below are NOT arbitrary and must
 * not be tweaked without re-checking the invariant they were chosen to
 * guarantee (see scoreToRiskTier's docstring).
 */

export interface SurveyOption {
  label: string;
  points: number;
}

export interface SurveyQuestion {
  id: "reaction" | "horizon" | "experience";
  prompt: string;
  options: readonly SurveyOption[];
}

/**
 * Q1 (reaction to an actual 5% drop) is the dominant signal by design --
 * its point range (0/2/4/6) is deliberately wider than Q2+Q3's combined
 * max (2+2=4). This isn't just "weighted higher" for emphasis; it's what
 * makes the 공격적-unreachable-without-a-calm-leaning-Q1-answer invariant
 * in scoreToRiskTier actually hold. Behavioral reaction to a real loss is
 * also simply a more direct risk-tolerance signal than a stated horizon
 * or self-reported experience level -- both of the latter are easy to
 * answer aspirationally ("I'd hold long-term") without it reflecting how
 * someone actually behaves when the number on screen turns red.
 */
export const SURVEY_QUESTIONS: readonly SurveyQuestion[] = [
  {
    id: "reaction",
    prompt: "갑자기 시장이 5% 하락하면 당신은?",
    options: [
      { label: "바로 매도한다", points: 0 },
      { label: "일부만 정리한다", points: 2 },
      { label: "지켜본다", points: 4 },
      { label: "오히려 더 산다", points: 6 },
    ],
  },
  {
    id: "horizon",
    prompt: "투자 기간을 얼마나 생각하고 계신가요?",
    options: [
      { label: "단기 (1년 이내)", points: 0 },
      { label: "중기 (1~3년)", points: 1 },
      { label: "장기 (3년 이상)", points: 2 },
    ],
  },
  {
    id: "experience",
    prompt: "투자 경험은 어느 정도이신가요?",
    options: [
      { label: "초보", points: 0 },
      { label: "경험 있음", points: 1 },
      { label: "능숙", points: 2 },
    ],
  },
] as const;

export const SURVEY_MAX_SCORE = SURVEY_QUESTIONS.reduce(
  (sum, q) => sum + Math.max(...q.options.map((o) => o.points)),
  0,
); // 10

/**
 * score = sum of each answered question's points, range 0-10.
 *
 * Thresholds (0-3 보수적 / 4-6 중립 / 7-10 공격적) were chosen, not just to
 * split the range evenly, to guarantee: 공격적 is unreachable unless Q1 is
 * "지켜본다" (4) or "오히려 더 산다" (6) -- the maximum reachable score with
 * any calmer Q1 answer is 2 (일부만 정리한다) + 2 (장기) + 2 (능숙) = 6,
 * which lands in 중립, never 공격적. Verified exhaustively over all 4x3x3
 * answer combinations (11 보수적 / 14 중립 / 11 공격적, no degenerate
 * clustering) before this was approved. The frontend has no test runner
 * configured yet, so that enumeration isn't re-checked by an executable
 * test -- treat any edit to the point values or thresholds above as
 * requiring the same by-hand enumeration before shipping.
 */
export function scoreToRiskTier(score: number): RiskTier {
  if (score <= 3) return "보수적";
  if (score <= 6) return "중립";
  return "공격적";
}

/** answers must be in SURVEY_QUESTIONS order, one points value per
 * question (not option index -- callers already have the selected
 * option's `points` at hand from rendering its options, no need to
 * re-look-up by index). */
export function computeRiskTier(answers: readonly number[]): RiskTier {
  const score = answers.reduce((sum, points) => sum + points, 0);
  return scoreToRiskTier(score);
}
