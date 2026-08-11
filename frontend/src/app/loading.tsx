/**
 * Shown automatically while page.tsx's async fetch is in flight. Matters
 * in practice: GET /api/regime/today can take ~10-15s on the first
 * request of a trading day (single-fit HMM + HRP, before the backend's
 * own daily cache kicks in) -- see api/pipeline.py's compute_today_snapshot.
 */
export default function HomeLoading() {
  return (
    <div className="flex flex-col gap-4">
      <div className="animate-pulse rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="h-4 w-28 rounded bg-card-2" />
        <div className="mx-auto mt-6 h-[140px] w-[200px] rounded-full bg-card-2" />
      </div>
      <div className="animate-pulse rounded-2xl border border-border bg-card p-5 shadow-card">
        <div className="h-4 w-24 rounded bg-card-2" />
        <div className="mx-auto mt-4 h-[180px] w-[180px] rounded-full bg-card-2" />
      </div>
      <p className="text-center font-mono text-[11px] uppercase tracking-[0.15em] text-muted-2">
        오늘의 국면 계산 중...
      </p>
    </div>
  );
}
