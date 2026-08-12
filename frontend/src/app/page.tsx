import Link from "next/link";
import { RadarGauge } from "@/components/RadarGauge";
import { AllocationDonut } from "@/components/AllocationDonut";
import { getRegimeToday } from "@/lib/api";

export default async function HomePage() {
  const today = await getRegimeToday();

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
        <h2 className="font-kr text-base font-medium text-text">오늘의 추천 배분</h2>
        <AllocationDonut weights={today.recommended_weights} className="mt-3" />
      </section>

      <Link
        href="/explainability"
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
