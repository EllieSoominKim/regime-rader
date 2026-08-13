/**
 * This route fetches /api/regime/today (up to ~14s cold) and
 * /api/backtest/summary (up to ~100s cold, once per trading day) in
 * parallel -- worst case is whichever is slower, not both stacked, but
 * still worth a real skeleton if this happens to be the first hit of
 * the day on either endpoint.
 */
export default function ExplainabilityLoading() {
  return (
    <div className="flex flex-col gap-4">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-border bg-card p-5 shadow-card">
          <div className="h-4 w-32 rounded bg-card-2" />
          <div className="mt-3 h-16 w-full rounded-xl bg-card-2" />
        </div>
      ))}
      <p className="text-center font-mono text-[11px] uppercase tracking-[0.15em] text-muted-2">
        설명 데이터 계산 중...
      </p>
    </div>
  );
}
