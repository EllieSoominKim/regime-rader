# regime-rader frontend

Next.js 14 (App Router, TypeScript, Tailwind) dashboard for regime-rader.
Talks to the FastAPI backend in `../api/`.

## Getting started

```bash
npm install
cp .env.example .env.local   # adjust NEXT_PUBLIC_API_BASE_URL if the backend isn't on :8000
npm run dev
```

The backend must be running separately (`../api/`, see its own README/docstrings) --
this app has no mock-data fallback by design; every screen reads real
`/api/regime/*`, `/api/hrp/*`, `/api/backtest/*` responses.

## Assets (`public/`)

- `icon_transparent_1024.png` -- the radar mark, used in the header next to
  the "regime-rader" wordmark text.
- `favicon_256.png` -- site favicon.
- `wordmark_horizontal.png` -- **not currently referenced anywhere.** The
  header renders "regime-rader" as live text (matches the mockup, and
  stays themeable/resizable) rather than this flattened image. Kept in
  `public/` reserved for a future spot that needs a single flattened
  lockup image rather than text + icon -- e.g. an OG/share-card image or
  an email header. Remove it if that need never materializes.

## Fonts

Loaded via `next/font/google`, no manual font files: Noto Sans KR
(400/500/900, Korean headlines/body) and JetBrains Mono (400/500/700,
data/numerals/HUD-style labels).
