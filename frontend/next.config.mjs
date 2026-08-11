/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Next 14.2 changed the client-side Router Cache's default for dynamic
    // routes (any route with a no-store fetch, like Home's
    // getRegimeToday()) to 0s -- every back/forward/Link navigation
    // re-hits the server, even seconds after the last visit in the same
    // session. Restoring a 30s window here means navigating away (e.g. to
    // /explainability) and back to Home within 30s reuses the cached RSC
    // payload instead of re-rendering server-side.
    //
    // This is NOT a fix for the cold-cache case (a genuine first-of-day
    // backend compute, ~10-15s, still happens exactly once per trading
    // day regardless -- see api/cache.py) -- it only removes REDUNDANT
    // round-trips once that day's data is already cached server-side,
    // which measured at 30-70ms end-to-end once warm. That's already
    // imperceptible on its own; this just removes it entirely for
    // same-session revisits. Deliberately not reaching for SWR/React
    // Query for this -- that would mean converting Home from a Server
    // Component (fast SSR first paint) to client-side fetching (blank
    // shell first, then a fetch), a worse trade for a problem this small.
    staleTimes: {
      dynamic: 30,
    },
  },
};

export default nextConfig;
