/**
 * GET /api/regime/history shares its ~85-100s once-daily cold compute
 * with /api/hrp/history and /api/backtest/summary (api/cache.py's shared
 * "daily_bundle" key) -- worth a real skeleton here, this is the slowest
 * cold path in the whole app.
 */
export default function HistoryLoading() {
  return (
    <div className="flex flex-col gap-4">
      <div className="animate-pulse rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="h-4 w-24 rounded bg-card-2" />
        <div className="mt-3 h-8 w-full rounded-xl bg-card-2" />
        <div className="mt-3 h-[220px] w-full rounded-xl bg-card-2" />
      </div>
      <div className="animate-pulse rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="h-4 w-20 rounded bg-card-2" />
        <div className="mt-3 h-[56px] w-full rounded-xl bg-card-2" />
      </div>
      <p className="text-center font-mono text-[11px] uppercase tracking-[0.15em] text-muted-2">
        국면 히스토리 계산 중... (최초 1회, 최대 약 100초)
      </p>
    </div>
  );
}
