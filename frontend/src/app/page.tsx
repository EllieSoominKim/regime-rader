import { cookies } from "next/headers";
import Link from "next/link";
import { RadarGauge } from "@/components/RadarGauge";
import { AllocationDonut } from "@/components/AllocationDonut";
import { getRegimeToday } from "@/lib/api";
import { resolveRiskTier, RISK_TIER_COOKIE, RISK_TIER_LABELS } from "@/lib/riskTier";

// [2026-08] risk_tier is read cookie-first, not from the URL alone --
// reading only searchParams (the URL) meant a cold load (fresh URL/
// bookmark/hard refresh) always rendered the 중립 default first, THEN
// flashed to the real tier once client-side JS (RiskTierSync) could run
// and correct the URL -- confirmed via SSR diff (see lib/riskTier.ts's
// module docstring). The cookie IS present on that very first request, so
// resolveRiskTier can get it right on the very first render, no flash.
// RiskTierSync (mounted once in the root layout) keeps both the cookie and
// the URL param in sync with localStorage as a secondary mechanism.
export default async function HomePage({
  searchParams,
}: {
  searchParams: { risk_tier?: string };
}) {
  const riskTier = resolveRiskTier(cookies().get(RISK_TIER_COOKIE)?.value, searchParams.risk_tier);
  const today = await getRegimeToday(riskTier);

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="flex items-baseline justify-between">
          <h1 className="font-kr text-base font-medium text-text">오늘의 위기 확률</h1>
          <span className="font-mono text-[11px] text-muted-2">{today.date}</span>
        </div>

        <RadarGauge
          crisisProbability={today.crisis_probability}
          caption={`국면 ${today.regime + 1} / ${today.selected_n_states}`}
          className="mt-2"
        />

        <p className="mt-1 text-center font-kr text-xs text-muted">
          국고채 3년물 변동성 기반 국면 판단 (BIC, {today.selected_n_states}개 상태 모델)
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="flex items-baseline justify-between">
          <h2 className="font-kr text-base font-medium text-text">오늘의 추천 배분</h2>
          {/* Contextual entry point into /onboarding, right where the tier
              actually changes what's shown -- see lib/riskSurvey.ts. Also
              the only re-diagnosis entry point besides the result screen's
              own "다시 진단하기" (per the plan: Home links to /onboarding,
              not just a not-yet-built settings screen). */}
          <Link href="/onboarding" className="font-mono text-[11px] text-muted-2">
            {RISK_TIER_LABELS[riskTier]} 기준
          </Link>
        </div>
        <AllocationDonut weights={today.recommended_weights} className="mt-3" />
      </section>

      <Link
        href={`/explainability?risk_tier=${encodeURIComponent(riskTier)}`}
        // [2026-08-13] Confirmed via integration testing: a client-side
        // Link navigation into /explainability could render with 중립's
        // numbers regardless of the actual risk-tier cookie -- reproduced
        // even with prefetch disabled and even immediately after a fresh
        // router.refresh(), so this isn't ONE specific cache layer we can
        // name and selectively invalidate; something in Next 14's
        // client-navigation request path for a cookies()-only-dynamic
        // route isn't reliably re-resolving the cookie the way a hard
        // reload or a direct request always correctly does (verified
        // repeatedly, including capturing the actual RSC response body).
        // Rather than keep chasing which internal cache is responsible,
        // this uses the one mechanism already PROVEN reliable throughout
        // that whole investigation: put the tier in the URL itself, same
        // as Home's own ?risk_tier= (see resolveRiskTier's cookie-first,
        // query-param-fallback order) -- a URL that changes with the tier
        // can't serve a same-URL cached/stale response for a different
        // tier, regardless of which layer would otherwise be at fault.
        prefetch={false}
        className="flex items-center justify-center gap-1.5 rounded-2xl border border-border bg-card-2 px-5 py-3.5 font-kr text-sm font-medium text-accent transition active:scale-[0.99]"
      >
        왜 이렇게 배분됐을까요?
        <span aria-hidden="true">→</span>
      </Link>

      {/* Temporary text-link nav until the full cross-screen shell (bottom
          tab bar, per the 5-screen product brief) is built. */}
      <Link
        href="/history"
        className="flex items-center justify-center gap-1 py-1 font-mono text-xs uppercase tracking-[0.1em] text-muted"
      >
        국면 히스토리 보기
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}
