# Contract: Advertiser App

Version 0.1, 30 Oct 2026. Between Experience (`apps/advertiser`) and Platform (`services/campaign-api`).

Version 0.1 is mock-first. The app is built against a typed client with a mock adapter (task 004). Platform implements these endpoints in Sprints 1-2, and the app switches over with one environment variable. Shapes can change before 1.0, but only through a planner task.

## Who the app is for

A café owner on a phone at 10pm. No marketing jargon, one decision per screen, and the bidding explained in one plain sentence wherever money is involved.

## The journey (screens)

| # | Screen | What happens | Calls |
|---|---|---|---|
| 1 | Sign up / log in | Email and password, or a magic link. Pick account type: business or creator | `POST /v1/auth/*` (mocked until Sprint 1) |
| 2 | About you | Business name, address (pinned on a map), category. Category drives compliance: alcohol, gambling and political are refused with a clear message | `PUT /v1/me/profile` |
| 3 | Home | Campaigns with status, wallet balance, "New campaign" | `GET /v1/me`, `GET /v1/campaigns`, `GET /v1/wallet` |
| 4a | New campaign: goal | Footfall near me / awareness in an area / an event date | - |
| 4b | Where | Map of screens with a radius around the business; tap screens to include or exclude | `GET /v1/screens?lat=&lng=&radius_m=` |
| 4c | When | Dates, plus time-of-day presets: morning commute, lunch, evening, all day | - |
| 4d | Budget | Total in EUR, with a live estimate of plays and impressions as a range, and a short "how bidding works" panel | `POST /v1/estimates` |
| 4e | Creative | Upload an image or video (spec checked instantly), or "make one for me" (studio placeholder in v0.1) | `POST /v1/creatives` |
| 4f | Review and pay | Compliance result (pass / fix needed / human review), price summary, pay from wallet, launch | `POST /v1/campaigns`, `POST /v1/campaigns/{id}/submit` |
| 5 | Campaign | Status timeline (submitted, compliance, media-owner approval, live, finished), plays, impressions, spend against budget, map of screens played | `GET /v1/campaigns/{id}`, `GET /v1/campaigns/{id}/report` |
| 6 | Wallet | Balance, top up, invoices | `GET /v1/wallet`, `POST /v1/wallet/topups` |
| 7 | Assistant | Chat with the Advertiser Agent, always labelled as AI | `POST /v1/agent/messages` |

## Shapes (v0.1)

Money is integer micros with a currency code. Dates are ISO 8601.

```ts
type Money = { micros: number; currency: "EUR" };

type Me = { id: string; email: string; account_type: "business" | "creator";
  profile?: { name: string; category: string; lat: number; lng: number; address: string } };

type Screen = { id: string; name: string; lat: number; lng: number; venue_type: string;
  format: "landscape_1920x1080" | "portrait_1080x1920"; media_owner: string };

type EstimateRequest = { screen_ids: string[]; start: string; end: string;
  dayparts: ("morning" | "lunch" | "evening" | "all_day")[]; budget: Money };
type Estimate = { plays_low: number; plays_high: number; impressions_low: number;
  impressions_high: number; note: string };

type CreativeCheck = { creative_id: string; ok: boolean; problems: string[];
  format?: Screen["format"]; duration_s?: number };

type ComplianceResult = { verdict: "pass" | "fix_needed" | "human_review";
  reasons: { rule: string; message: string }[] };

type CampaignStatus = "draft" | "submitted" | "compliance_review" | "awaiting_media_owner"
  | "live" | "paused" | "finished" | "rejected";

type Campaign = { id: string; name: string; status: CampaignStatus; goal: string;
  screen_ids: string[]; start: string; end: string; dayparts: string[];
  budget: Money; spent: Money; creative_id?: string; compliance?: ComplianceResult };

type Report = { plays: number; impressions: number; spent: Money;
  by_screen: { screen_id: string; plays: number; impressions: number }[];
  first_event_at?: string; last_event_at?: string };

type Wallet = { balance: Money; invoices: { id: string; date: string; amount: Money; url: string }[] };

type AgentMessage = { role: "user" | "agent"; text: string; created_at: string };
```

## Rules for the app

- **Honest numbers.** While on the mock adapter, every screen shows a visible "Demo data" banner. Estimates are always ranges, never a single promise.
- **AI is labelled.** The Assistant screen and any AI-made creative say so.
- **Accessible and mobile-first.** Works at 375px wide, keyboard reachable, readable contrast.
- **Same UI kit as `apps/web`** (Tailwind, shadcn-style components) for one look across both apps.
