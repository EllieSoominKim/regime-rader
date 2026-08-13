"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { DEFAULT_RISK_TIER, getStoredRiskTier, setStoredRiskTier } from "@/lib/riskTier";

/**
 * [2026-08] Historical note: this component used to be the ONLY mechanism
 * carrying the stored risk tier from localStorage to the Server Component
 * pages, via a post-mount router.replace onto the URL's `risk_tier` query
 * param. That has a confirmed flash-of-wrong-numbers bug on every cold
 * load (fresh URL/bookmark/hard refresh): the first server render always
 * happens before this effect can run (useEffect fires after paint, by
 * React's own execution model -- not a timing fluke), so a returning
 * 공격적-tier user would see 중립's allocation numbers for one frame before
 * they snapped to the correct ones. See lib/riskTier.ts's module docstring
 * for the SSR diff that caught it (4.9% vs 7.9%).
 *
 * Fixed at the source: pages now read the risk tier from a COOKIE during
 * their initial server render (resolveRiskTier + next/headers' cookies()),
 * which unlike localStorage IS present on that very first request. This
 * component's job shrinks accordingly to two secondary responsibilities,
 * neither of which should fire on a normal repeat visit once the cookie is
 * warm:
 *   1. Self-heal the cookie from localStorage, for a browser session that
 *      predates this fix (cookie never written) or had it cleared
 *      independently of localStorage.
 *   2. Keep the URL's `risk_tier` query param in sync too, so a shared/
 *      bookmarked link carries the tier explicitly even before any cookie
 *      exists on the receiving browser (resolveRiskTier's fallback order
 *      is cookie > query param > 중립).
 */
export function RiskTierSync() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    const stored = getStoredRiskTier();
    const current = searchParams.get("risk_tier");
    if (current === stored) return;
    // Common case: nothing stored yet (first-time visitor) and no param on
    // the URL either -- both sides already agree on 중립 via their own
    // defaults (getStoredRiskTier / parseRiskTier), so writing it into the
    // URL would just cost a needless replace+refetch on every single page
    // load for the majority of visitors.
    if (current === null && stored === DEFAULT_RISK_TIER) return;

    // Re-affirm both stores (localStorage no-op, cookie (re)written) --
    // this is what actually self-heals a stale/missing cookie; without it
    // a browser whose cookie fell out of sync would keep re-running this
    // whole effect on every navigation instead of settling.
    setStoredRiskTier(stored);

    const params = new URLSearchParams(searchParams.toString());
    params.set("risk_tier", stored);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    // Re-run whenever the route or query changes (e.g. link nav resets
    // searchParams) so the stored tier stays reflected on every page, not
    // just the one mounted at app load.
  }, [pathname, searchParams, router]);

  return null;
}
