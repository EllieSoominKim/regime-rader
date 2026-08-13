/**
 * Client-side risk-tier persistence. There's no user-accounts/backend
 * persistence layer in this MVP (see RegimeConditionalHRP.RISK_TIERS'
 * own docstring), so the tier a user picks in onboarding lives in
 * localStorage AND a cookie, and travels as a query param on every
 * /api/regime/today request -- see lib/api.ts's getRegimeToday.
 *
 * [2026-08] Why both localStorage AND a cookie, not just localStorage:
 * localStorage is invisible to the server on the very first request of a
 * page load (fresh URL, bookmark, hard refresh) -- the Server Component
 * page has already fetched /api/regime/today and rendered with the
 * default 중립 tier by the time any client-side JS (RiskTierSync) gets a
 * chance to run and correct it, producing a real, visible flash of wrong
 * allocation numbers (e.g. 4.9% -> 7.9%) right after first paint. A
 * confirmed bug, not a theoretical one -- see the SSR diff that caught it
 * (curling "/" vs "/?risk_tier=공격적" showed exactly that 4.9/7.9 split).
 * Cookies, unlike localStorage, ARE sent on that very first request, so
 * the Server Component can read the tier before it ever renders --
 * eliminating the flash instead of racing to fix it after the fact. Both
 * stores are kept in sync (see setStoredRiskTier); RiskTierSync's
 * URL-param sync stays as a secondary mechanism for shareable links and to
 * self-heal a cookie that predates this fix or got cleared independently
 * of localStorage.
 */

export type RiskTier = "보수적" | "중립" | "공격적";
export const RISK_TIERS: RiskTier[] = ["보수적", "중립", "공격적"];
export const DEFAULT_RISK_TIER: RiskTier = "중립";

const STORAGE_KEY = "regime-rader:risk-tier";

/** Also the Server Component-side cookie name (see resolveRiskTier) --
 * one shared constant so the client write and the server read can never
 * drift to different names. Not httpOnly/secure-flagged: this is a
 * non-sensitive UI preference that the client must also read back
 * (getStoredRiskTier still prefers localStorage), not an auth token. */
export const RISK_TIER_COOKIE = "regime-rader-risk-tier";

function isRiskTier(value: unknown): value is RiskTier {
  return typeof value === "string" && (RISK_TIERS as string[]).includes(value);
}

/** Defaults to 중립 for a first-time visitor who hasn't completed
 * onboarding yet (or on the server, where localStorage doesn't exist --
 * callers must only invoke this client-side, e.g. inside useEffect). */
export function getStoredRiskTier(): RiskTier {
  if (typeof window === "undefined") return DEFAULT_RISK_TIER;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return isRiskTier(raw) ? raw : DEFAULT_RISK_TIER;
}

/** Writes BOTH localStorage (client-side reads, e.g. re-populating a
 * tier-selection UI) and the cookie (server-side reads, e.g.
 * resolveRiskTier below) -- see this module's docstring for why the
 * cookie exists at all. 1-year max-age: this is a standing preference,
 * not a session value; samesite=lax is enough since it's never used for
 * anything security-sensitive and still needs to ride along on a plain
 * top-level navigation (typed URL/bookmark) for the flash-elimination to
 * actually work on a fresh tab. */
export function setStoredRiskTier(tier: RiskTier): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, tier);
  document.cookie = `${RISK_TIER_COOKIE}=${tier}; path=/; max-age=31536000; samesite=lax`;
}

/** Server-safe counterpart to getStoredRiskTier: validates a raw
 * `?risk_tier=` searchParams value (Next.js hands these in as
 * `string | string[] | undefined`) instead of reading localStorage, since
 * server components can't see localStorage at all -- see
 * components/RiskTierSync.tsx for how the client-persisted tier gets onto
 * the URL in the first place. Falls back to 중립 for anything unrecognized,
 * same as getStoredRiskTier. */
export function parseRiskTier(value: string | string[] | undefined): RiskTier {
  const first = Array.isArray(value) ? value[0] : value;
  return isRiskTier(first) ? first : DEFAULT_RISK_TIER;
}

/** The Server Component page's actual resolution order for a request:
 * cookie (available on the very first request, before any client JS runs
 * -- see this module's docstring) > URL query param (RiskTierSync's
 * fallback sync mechanism, and what makes a shared/bookmarked link with
 * an explicit ?risk_tier= work even with no cookie yet) > 중립 default.
 * Call from a Server Component with `cookies().get(RISK_TIER_COOKIE)?.value`
 * (next/headers) -- kept out of THIS file since next/headers can't be
 * imported anywhere a Client Component (RiskTierSync) also imports from. */
export function resolveRiskTier(
  cookieValue: string | undefined,
  searchParamValue: string | string[] | undefined,
): RiskTier {
  if (isRiskTier(cookieValue)) return cookieValue;
  return parseRiskTier(searchParamValue);
}

export const RISK_TIER_LABELS: Record<RiskTier, string> = {
  보수적: "보수적",
  중립: "중립",
  공격적: "공격적",
};

/**
 * One-line, honest disclaimer per tier for the onboarding survey's
 * tier-selection UI (survey screen itself not yet built -- these are
 * ready for it). 공격적's disclaimer exists specifically because that
 * tier keeps a real, non-zero growth-asset floor even at
 * crisis_probability=0.98 (RegimeConditionalHRP.RISK_TIERS["공격적"]
 * ["crisis_growth_min"]=0.02) -- an 공격적-tier user WILL experience a
 * real, bounded-not-eliminated drawdown in a genuine crisis if growth
 * assets crash. That tradeoff must be disclosed at tier-selection time,
 * not discovered during an actual crisis.
 */
export const RISK_TIER_DISCLAIMERS: Record<RiskTier, string> = {
  보수적: "위기 상황에서 안전자산 비중을 가장 적극적으로 높입니다 — 대신 평소에도 성장자산 비중이 낮아요.",
  중립: "위기 확률에 따라 안전자산과 성장자산 비중이 균형 있게 조정됩니다.",
  공격적:
    "위기 상황에서도 일정 부분 성장자산을 유지합니다 — 방어 효과가 보수적/중립 대비 제한적일 수 있어요.",
};
