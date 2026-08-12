import { BacktestMetricsTable } from "@/components/BacktestMetricsTable";
import { CumulativeReturnChart } from "@/components/CumulativeReturnChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import { buildEquityCurve } from "@/lib/backtestHistory";
import { getBacktestSummary } from "@/lib/api";

export default async function BacktestPage() {
  const { real_backtest } = await getBacktestSummary();
  const { regime_hrp, benchmark_6040 } = real_backtest.full_window;
  const equityCurve = buildEquityCurve(real_backtest.daily_returns);

  const mddRatio = Math.abs(benchmark_6040.mdd) / Math.abs(regime_hrp.mdd);
  const volRatio = benchmark_6040.annualized_vol / regime_hrp.annualized_vol;
  const returnWinner = benchmark_6040.total_return > regime_hrp.total_return ? "60/40" : "Regime-HRP";
  const sharpeWinner = benchmark_6040.sharpe > regime_hrp.sharpe ? "60/40" : "Regime-HRP";
  const calmarWinner = benchmark_6040.calmar > regime_hrp.calmar ? "60/40" : "Regime-HRP";

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="flex items-baseline justify-between">
          <h1 className="font-kr text-base font-medium text-text">백테스트 비교</h1>
          <span className="font-mono text-[11px] text-muted-2">
            {real_backtest.window_start} ~ {real_backtest.window_end}
          </span>
        </div>
        <p className="mt-0.5 font-kr text-xs text-muted">{real_backtest.n_days}거래일, 실제 데이터</p>

        <BacktestMetricsTable regimeHrp={regime_hrp} benchmark6040={benchmark_6040} className="mt-4" />

        <p className="mt-4 rounded-xl bg-card-2 p-3 font-kr text-xs leading-relaxed text-text">
          <strong>{returnWinner}</strong>가 수익률에서, <strong>{sharpeWinner}</strong>가 샤프비율에서,{" "}
          <strong>{calmarWinner}</strong>가 칼마비율에서 앞섰습니다 — 이번 표본에서는 위험조정 수익
          기준으로도 60/40이 우세합니다. Regime-HRP의 우위는 변동성({volRatio.toFixed(1)}배 작음)과
          최대낙폭({mddRatio.toFixed(1)}배 작음), 즉 <strong>실제로 경험한 손실의 크기</strong>에
          있습니다.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-card p-5 shadow-card">
        <h2 className="font-kr text-base font-medium text-text">누적 수익률</h2>
        <CumulativeReturnChart data={equityCurve} className="mt-3" />

        <h2 className="mt-5 font-kr text-base font-medium text-text">낙폭 비교 (Underwater)</h2>
        <DrawdownChart data={equityCurve} className="mt-3" />

        <p className="mt-3 font-kr text-xs leading-relaxed text-muted">
          붉은 음영 구간은 위기 확률이 66% 이상이었던 기간입니다. 이 표본에서는 위기 신호가 실제
          주식 급락과 겹치지 않았습니다 — 국고채 금리 변동성 기반 신호가 이번 표본에서는 주식시장
          스트레스를 직접 예측하지 못했다는 뜻입니다.
        </p>
      </section>
    </div>
  );
}
