import Link from "next/link";

/**
 * Stub route target for Home's "왜 이렇게 배분됐을까요?" link -- the real
 * 설명가능성 카드 (explainability card) screen is built in a later pass.
 */
export default function ExplainabilityPage() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-card">
      <h1 className="font-kr text-base font-medium text-text">설명가능성 카드</h1>
      <p className="mt-2 font-kr text-sm text-muted">곧 제공됩니다.</p>
      <Link
        href="/"
        className="mt-4 inline-block font-mono text-xs uppercase tracking-[0.1em] text-accent"
      >
        ← Back
      </Link>
    </div>
  );
}
