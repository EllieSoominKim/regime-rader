"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SURVEY_QUESTIONS, computeRiskTier } from "@/lib/riskSurvey";
import { RISK_TIER_DISCLAIMERS, RISK_TIER_LABELS, setStoredRiskTier, type RiskTier } from "@/lib/riskTier";

/**
 * Onboarding risk-tolerance survey -- see lib/riskSurvey.ts for the
 * question set and scoring rule (approved 2026-08-13). No server data
 * needed (nothing here reads /api/*), so this is a plain client component,
 * not the async-server-page + client-view split used by history/page.tsx
 * (that split exists there specifically to fetch data server-side while
 * keeping the range-tab interactivity client-side; there's no data-fetch
 * half here to split off).
 *
 * Deliberately NOT a shared new "wizard" primitive -- per the plan, this
 * screen reuses the app's existing card/button visual language
 * (rounded-2xl border-border bg-card, the bg-card-2/text-accent
 * selected-state convention from TimeRangeTabs, the same CTA button
 * styling as Home's explainability link) rather than introducing a new
 * component family for what is, so far, exactly one screen.
 */

type Step = number | "result";

function ProgressDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`h-2 rounded-full transition-all ${
            i === current ? "w-5 bg-accent" : i < current ? "w-2 bg-accent" : "w-2 bg-card-2"
          }`}
        />
      ))}
    </div>
  );
}

function OptionButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`w-full rounded-2xl border px-4 py-3.5 text-left font-kr text-sm transition active:scale-[0.99] ${
        selected ? "border-accent bg-card-2 font-medium text-accent" : "border-border bg-card text-text"
      }`}
    >
      {label}
    </button>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(0);
  // One entry per question, in SURVEY_QUESTIONS order; null = unanswered
  // yet. Holds the selected option's `points` directly (not an option
  // index) -- computeRiskTier just sums this array, no re-lookup needed.
  const [answers, setAnswers] = useState<(number | null)[]>(
    () => SURVEY_QUESTIONS.map(() => null),
  );

  function selectOption(points: number) {
    if (step === "result") return;
    setAnswers((prev) => {
      const next = [...prev];
      next[step] = points;
      return next;
    });
  }

  function goNext() {
    if (step === "result") return;
    const isLastQuestion = step === SURVEY_QUESTIONS.length - 1;
    setStep(isLastQuestion ? "result" : step + 1);
  }

  function restart() {
    setAnswers(SURVEY_QUESTIONS.map(() => null));
    setStep(0);
  }

  function start(tier: RiskTier) {
    // Writes both localStorage and the risk-tier cookie (see
    // lib/riskTier.ts) -- the cookie is what lets Home's Server Component
    // render the correct tier on the very first request, no flash (see
    // the cold-load fix). The explicit ?risk_tier= query param is a
    // belt-and-suspenders fallback for a browser that happens to block
    // the cookie write, matching resolveRiskTier's own fallback order.
    setStoredRiskTier(tier);
    // [2026-08-13] router.refresh() invalidates the current route's cached
    // data as defense-in-depth for the tier that just changed -- cheap and
    // correct to call here regardless. It is NOT sufficient on its own for
    // routes reached from further navigation, though: integration testing
    // found a route with a static URL (no query param, e.g.
    // /explainability) could keep rendering the PREVIOUS tier's data on a
    // client-side Link click even with this refresh() in place and even
    // with prefetch disabled on that Link -- reproduced repeatedly,
    // including capturing the actual RSC response body Next served. Home
    // itself was never affected, but only because its own URL's
    // ?risk_tier= query already differs on every push here, not because of
    // anything this refresh() does. The actual fix for a downstream route
    // like /explainability is to give ITS Link the same ?risk_tier= query
    // param (see app/page.tsx's Link to /explainability) so its cache key
    // differs too -- see that file's comment for the full investigation.
    router.refresh();
    router.push(`/?risk_tier=${encodeURIComponent(tier)}`);
  }

  if (step === "result") {
    const tier = computeRiskTier(answers.filter((p): p is number => p !== null));
    return (
      <div className="flex flex-col gap-4">
        <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h1 className="font-kr text-base font-medium text-text">당신의 투자 성향은</h1>
          <p className="mt-3 text-center font-kr text-2xl font-bold text-accent">
            {RISK_TIER_LABELS[tier]}
          </p>
          <p className="mt-3 font-kr text-sm leading-relaxed text-muted">
            {RISK_TIER_DISCLAIMERS[tier]}
          </p>
        </section>

        <button
          type="button"
          onClick={() => start(tier)}
          className="flex items-center justify-center gap-1.5 rounded-2xl border border-border bg-card-2 px-5 py-3.5 font-kr text-sm font-medium text-accent transition active:scale-[0.99]"
        >
          시작하기
          <span aria-hidden="true">→</span>
        </button>

        {/* The only current way to change tiers, so this stays a visible
            one-liner on the result screen itself -- not tucked into a
            settings screen that doesn't exist yet. Resets local state
            rather than navigating to /onboarding: this component is
            already mounted at that route, and a Next.js Link to the same
            pathname wouldn't remount it / clear this component's answers
            on its own. */}
        <button
          type="button"
          onClick={restart}
          className="flex items-center justify-center gap-1 py-1 font-mono text-xs uppercase tracking-[0.1em] text-muted"
        >
          다시 진단하기
        </button>
      </div>
    );
  }

  const question = SURVEY_QUESTIONS[step];
  const selected = answers[step];
  const isLastQuestion = step === SURVEY_QUESTIONS.length - 1;

  return (
    <div className="flex flex-col gap-4">
      <ProgressDots total={SURVEY_QUESTIONS.length} current={step} />

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h1 className="font-kr text-base font-medium text-text">{question.prompt}</h1>

        <div className="mt-4 flex flex-col gap-2">
          {question.options.map((option) => (
            <OptionButton
              key={option.label}
              label={option.label}
              selected={selected === option.points}
              onClick={() => selectOption(option.points)}
            />
          ))}
        </div>
      </section>

      <button
        type="button"
        onClick={goNext}
        disabled={selected === null}
        className="w-full rounded-2xl border border-border bg-card-2 px-5 py-3.5 font-kr text-sm font-medium text-accent transition active:scale-[0.99] disabled:pointer-events-none disabled:opacity-40"
      >
        {isLastQuestion ? "결과 보기" : "다음"}
      </button>

      <Link
        href="/"
        className="flex items-center justify-center gap-1 py-1 font-mono text-xs uppercase tracking-[0.1em] text-muted"
      >
        ← 홈으로
      </Link>
    </div>
  );
}
