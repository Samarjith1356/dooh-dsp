---
id: 004
title: Advertiser App skeleton, every screen working on demo data
lane: experience
status: building
depends_on: []
extra_review: []
branch: task/004-advertiser-app-skeleton
written: 2026-10-30
---

# 004: Advertiser App skeleton, every screen working on demo data

## Why
The Advertiser App is what customers will see and pay through, and today it doesn't exist. Building every screen now against the agreed contract means that Sprint 2 only swaps demo data for real data. It also gives Sam something to click through and show pilot customers.

## Context
- **The spec:** `contracts/advertiser-app.md`, covering the journey, the screens, the data shapes and the rules
- Product background: `handbook/01-mission-and-product.md`
- UI kit to match: `apps/web` (Tailwind config, `components/ui/*`, Leaflet map in `components/blocks/spatial-map.tsx`)

## Files you may touch
- `apps/advertiser/**` (new)

## Scope
1. Create a new Next.js 15 app (App Router, TypeScript, Tailwind) in `apps/advertiser`, running on port 3001. Copy the UI primitives from `apps/web/components/ui` rather than importing across apps.
2. Add a typed API client, `lib/api.ts`, with the contract's types and one function per call. Add a mock adapter, `lib/mock.ts`, selected by `NEXT_PUBLIC_API_MODE=mock` (the default). Give it around 10 demo Dublin screens and demo campaigns, all labelled as demo.
3. Build screens 1-7 from the contract, all working on the mock:
   - Sign-up with a business/creator choice
   - Profile with a category check: alcohol, gambling and political are refused with a clear message, and the user can't create a campaign
   - Home
   - The six-step new-campaign wizard, with a map, dayparts, a budget with a live range estimate, and creative upload with the spec check
   - Review, with all three compliance outcomes reachable in demo mode
   - The campaign page with its status timeline
   - Wallet
   - Assistant, with mock replies and a clear "AI" label
4. Use this text for the "how bidding works" panel: *"You set a budget. Whenever one of your screens has a free slot, we bid for it automatically. You only pay when your ad actually plays, and never more than your budget."*
5. Show a "Demo data" banner on every screen while in mock mode.
6. Keep mock state in memory, with an optional `localStorage` save wrapped in try/catch.
7. Add `apps/advertiser/README.md`: how to run it, and how to switch to the real API later.
8. Add a Playwright smoke test (`npm run test:e2e`) that walks sign-up, a full new campaign and the Home list.

## Out of scope
- Real login, payments and backend changes (Sprints 1-2)
- AI creative generation (Sprint 4). "Make one for me" shows "coming soon"
- Final branding. The company name is not chosen yet, so use "Advertiser App" as a placeholder

## Acceptance criteria
- [ ] `npm run build` and `npm run test:e2e` pass in `apps/advertiser`
- [ ] Every screen is reachable from Home. Finishing the wizard adds the new campaign to Home
- [ ] The creative check rejects a 1000x1000 image and a 20-second video with clear messages, and accepts a 1920x1080 PNG
- [ ] Choosing alcohol, gambling or political as the category shows the refusal and blocks campaign creation
- [ ] The estimate is shown as a range and updates when the budget changes
- [ ] The demo banner shows on every screen in mock mode, and the Assistant is labelled AI
- [ ] The layout works at 375px and 1280px wide, with no horizontal scrolling at 375px
- [ ] No number is presented as real while the app runs on mock data

## Tests
```
cd apps/advertiser && npm install && npm run build && npm run test:e2e
```

## Open questions
_None yet._

---

## Builder report
_Filled in by Cursor._

## Review
_Filled in by Claude Code._
