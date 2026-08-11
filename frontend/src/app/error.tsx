"use client";

/**
 * Catches getRegimeToday() throwing (backend unreachable / non-2xx) --
 * see lib/api.ts's apiFetch for the error message shape this renders.
 */
export default function HomeError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <h2 className="font-kr text-base font-medium text-crisis">데이터를 불러오지 못했습니다</h2>
      <p className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-muted">
        {error.message}
      </p>
      <button
        onClick={() => reset()}
        className="mt-4 rounded-xl border border-border bg-card-2 px-4 py-2 font-kr text-sm text-text"
      >
        다시 시도
      </button>
    </div>
  );
}
