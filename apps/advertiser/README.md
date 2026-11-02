# Advertiser App

Customer-facing Next.js app for planning outdoor screen campaigns. Built against `contracts/advertiser-app.md`.

## Run locally

```bash
cd apps/advertiser
npm install
npm run dev
```

Opens on [http://localhost:3001](http://localhost:3001).

Default mode is **mock** (`NEXT_PUBLIC_API_MODE=mock`). Every screen shows a **Demo data** banner. Numbers are sample only.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on port 3001 |
| `npm run build` | Production build |
| `npm run start` | Serve the production build on 3001 |
| `npm run test:e2e` | Playwright smoke: sign-up → new campaign → Home |

First e2e run may need browsers:

```bash
npx playwright install chromium
```

## Switch to the real API later

1. Platform implements the endpoints in `contracts/advertiser-app.md`.
2. Set in `.env.local`:

```bash
NEXT_PUBLIC_API_MODE=live
NEXT_PUBLIC_API_BASE_URL=https://your-campaign-api.example
```

3. Replace the stub in `lib/api.ts` (`loadLive`) with a fetch client that uses the same types and function names as the mock adapter in `lib/mock.ts`.

Until then, keep `NEXT_PUBLIC_API_MODE=mock` (or omit it).
