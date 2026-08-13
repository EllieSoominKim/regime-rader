import { cookies } from "next/headers";
import Link from "next/link";
import { RadarGauge } from "@/components/RadarGauge";
import { getBacktestSummary, getRegimeToday, type AssetKey } from "@/lib/api";
import {
  assetLabel,
  computeDelta,
  formatPercent,
  formatVolatilityContext,
  stateLabel,
  volatilityLevel,
} from "@/lib/explainability";
import { resolveRiskTier, RISK_TIER_COOKIE } from "@/lib/riskTier";

const ASSET_ORDER: AssetKey[] = ["stocks", "bonds", "cash", "gold"];

function DeltaBadge({ current, previous }: { current: number; previous: number | null }) {
  const delta = computeDelta(current, previous);
  if (!delta) return null;
  const color = delta.direction === "up" ? "text-crisis" : delta.direction === "down" ? "text-calm" : "text-muted";
  const arrow = delta.direction === "up" ? "▲" : delta.direction === "down" ? "▼" : "•";
  return (
    <span className={`font-mono text-xs font-medium ${color}`}>
      {arrow} {Math.abs(delta.deltaPoints).toFixed(1)}%p
    </span>
  );
}

function MiniMagnitudeBar({ label, value, maxAbsValue }: { label: string; value: number; maxAbsValue: number }) {
  const widthPct = maxAbsValue > 0 ? (Math.abs(value) / maxAbsValue) * 100 : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 font-mono text-[10px] text-muted-2">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-card-2">
        <div className="h-full rounded-full bg-crisis" style={{ width: `${Math.max(2, widthPct)}%` }} />
      </div>
      <span className="w-12 shrink-0 text-right font-mono text-[10px] text-muted">{formatPercent(value)}</span>
    </div>
  );
}

// [2026-08] risk_tier is read cookie-first (see app/page.tsx's own comment
// for why -- same resolveRiskTier/RiskTierSync mechanism, cookie eliminates
// the cold-load flash that URL-only resolution had). getBacktestSummary is
// NOT tier-scoped (backtest/synthetic-stress always run at 중립 -- see
// api/pipeline.py's WalkForwardHRPEngine.run, which never takes a
// risk_tier argument), so only the getRegimeToday call below changes.
export default async function ExplainabilityPage({
  searchParams,
}: {
  searchParams: { risk_tier?: string };
}) {
  const riskTier = resolveRiskTier(cookies().get(RISK_TIER_COOKIE)?.value, searchParams.risk_tier);
  const [today, backtest] = await Promise.all([getRegimeToday(riskTier), getBacktestSummary()]);
  const { regime_hrp, benchmark_6040 } = backtest.real_backtest.full_window;
  const mddRatio = Math.abs(benchmark_6040.mdd) / Math.abs(regime_hrp.mdd);

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Headline */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="flex items-baseline justify-between">
          <h1 className="font-kr text-base font-medium text-text">왜 이렇게 배분됐을까요?</h1>
          <span className="font-mono text-[11px] text-muted-2">{today.date}</span>
        </div>

        <RadarGauge
          crisisProbability={today.crisis_probability}
          caption={`국면 ${today.regime + 1} / ${today.selected_n_states}`}
          className="mt-2"
        />

        {today.previous_date && today.previous_crisis_probability !== null ? (
          <p className="mt-1 text-center font-kr text-xs text-muted">
            전일({today.previous_date}) {formatPercent(today.previous_crisis_probability)} → 오늘{" "}
            {formatPercent(today.crisis_probability)}{" "}
            <DeltaBadge current={today.crisis_probability} previous={today.previous_crisis_probability} />
          </p>
        ) : null}
      </section>

      {/* 2a. 금리 변동성 */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">이유 1 · 금리 변동성</h2>
        <p className="mt-2 font-kr text-sm leading-relaxed text-text">
          이 신호는 <strong>국고채 3년물 금리의 변동성</strong>을 바탕으로 계산됩니다. 주식시장 자체의
          변동성이 아닙니다.
        </p>
        <p className="mt-2 font-kr text-sm leading-relaxed text-muted">
          오늘 금리 변동성 수준: <strong className="text-text">{volatilityLevel(today.conditional_volatility_percentile)}</strong> —{" "}
          {formatVolatilityContext(today.conditional_volatility_percentile)}.
        </p>
        <p className="mt-2 font-kr text-sm leading-relaxed text-muted">
          다만 국면 판단은 하루치 변동성의 크기만이 아니라 최근 며칠간의 흐름을 함께 봅니다. 그래서
          오늘 하루의 수치가 높다고 해서 곧바로 위기 국면으로, 낮다고 해서 곧바로 안정 국면으로
          분류되지는 않습니다.
        </p>

        <div className="mt-3 flex flex-col gap-1.5">
          {today.state_probabilities.map((p, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-10 shrink-0 font-kr text-xs text-muted">
                {stateLabel(i, today.selected_n_states)}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-card-2">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(1, p * 100)}%` }} />
              </div>
              <span className="w-10 shrink-0 text-right font-mono text-xs text-muted">{formatPercent(p)}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 2b. 국면조건부 배분 조정 */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">이유 2 · 국면조건부 배분 조정</h2>
        <p className="mt-2 font-kr text-sm leading-relaxed text-text">
          위기 확률이 높아질수록 채권·현금 같은 안전자산 비중의 상한이 자동으로 넓어지고, 주식·금 같은
          성장자산의 최소 비중은 낮아집니다.
        </p>

        {today.previous_combined_defensive_weight !== null ? (
          <p className="mt-2 font-kr text-sm text-muted">
            안전자산(채권+현금) 비중: {formatPercent(today.previous_combined_defensive_weight)} →{" "}
            <strong className="text-text">{formatPercent(today.combined_defensive_weight)}</strong>{" "}
            <DeltaBadge current={today.combined_defensive_weight} previous={today.previous_combined_defensive_weight} />
          </p>
        ) : null}

        <div className="mt-3 flex flex-col gap-1.5">
          {ASSET_ORDER.map((asset) => {
            const prev = today.previous_recommended_weights?.[asset] ?? null;
            const cur = today.recommended_weights[asset] ?? 0;
            return (
              <div key={asset} className="flex items-center justify-between font-kr text-xs">
                <span className="text-muted">{assetLabel(asset)}</span>
                <span className="font-mono text-text">
                  {prev !== null ? `${formatPercent(prev)} → ` : ""}
                  {formatPercent(cur)}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. 한계 -- 무엇을 포착하고, 무엇을 포착하지 못하는가 */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">이 신호가 포착하는 것 / 포착하지 못하는 것</h2>

        <div className="mt-3 rounded-xl bg-card-2 p-3">
          <p className="font-kr text-sm font-medium text-calm">✓ 포착하는 것</p>
          <p className="mt-1 font-kr text-sm leading-relaxed text-text">
            국고채 3년물 금리 변동성이 갑자기 커지는 금리시장 스트레스 상황.
          </p>
        </div>

        <div className="mt-2 rounded-xl bg-card-2 p-3">
          <p className="font-kr text-sm font-medium text-crisis">✗ 포착하지 못하는 것</p>
          <p className="mt-1 font-kr text-sm leading-relaxed text-text">
            주식시장 자체의 급락. 실제 백테스트에서 금리 변동성 위기와 주식시장 급락이{" "}
            <strong>항상 함께 나타나지는 않았습니다.</strong> 그래서 이 신호가 안정적이라고 해서
            주식시장이 반드시 안전한 것은 아니며, 반대의 경우도 마찬가지입니다.
          </p>
        </div>

        <Link
          href="/backtest"
          className="mt-3 inline-block font-mono text-xs uppercase tracking-[0.1em] text-accent"
        >
          백테스트에서 직접 확인하기 →
        </Link>
      </section>

      {/* 4. 근거 -- 실제 백테스트 수치 */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">이 방식이 실제로 하는 일</h2>
        <p className="mt-2 font-kr text-sm leading-relaxed text-text">
          실제 백테스트({backtest.real_backtest.window_start} ~ {backtest.real_backtest.window_end})에서
          regime-HRP는 60/40 대비 수익률과 샤프비율은 낮았지만, 최대낙폭은{" "}
          <strong>{mddRatio.toFixed(1)}배 작았습니다</strong> — 손실을 예방한 것이 아니라, 손실의 크기를
          줄였다는 뜻입니다.
        </p>

        <div className="mt-3 flex flex-col gap-2">
          <MiniMagnitudeBar
            label="Regime-HRP"
            value={regime_hrp.mdd}
            maxAbsValue={Math.max(Math.abs(regime_hrp.mdd), Math.abs(benchmark_6040.mdd))}
          />
          <MiniMagnitudeBar
            label="60/40"
            value={benchmark_6040.mdd}
            maxAbsValue={Math.max(Math.abs(regime_hrp.mdd), Math.abs(benchmark_6040.mdd))}
          />
        </div>

        <Link href="/backtest" className="mt-3 inline-block font-mono text-xs uppercase tracking-[0.1em] text-accent">
          전체 백테스트 결과 보기 →
        </Link>
      </section>

      <Link
        href="/"
        className="flex items-center justify-center gap-1 py-1 font-mono text-xs uppercase tracking-[0.1em] text-muted"
      >
        ← 홈으로
      </Link>
    </div>
  );
}
