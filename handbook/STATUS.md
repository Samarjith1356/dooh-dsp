# Status

Updated by the planner after every merge. Last update: 31 Oct 2026, 00:45.

**Current sprint:** Sprint 0, Foundations (2-13 Nov 2026), started early on 30 Oct.
**Priority order:** `tasks/BACKLOG.md` (D-013). **Build log:** `docs/build-log.csv`.

## Board

| Task | Lane | Priority | Status | Can start when |
|---|---|---|---|---|
| [003 Book spend on plays, not bids](../tasks/003-spend-on-billing.md) | Trading | P0 | in review, round 2 (security fixes pushed 19:39) | - |
| [006 Brain seeding without a database (CI green)](../tasks/006-brain-seed-offline.md) | Trading | P0 | ready | after 003 frees the Trading lane |
| [004 Advertiser App skeleton](../tasks/004-advertiser-app-skeleton.md) | Experience | P0 | in review, round 2 (fixes pushed 19:44) | - |
| [005 EUR across the stack](../tasks/005-eur.md) | Platform (other lanes pause) | P0 | waiting | 003, 004 merged |
| [001 KPIs from one full-window query](../tasks/001-kpi-full-window.md) | Platform | P1 | ready | now (002 merged) |

Next to be written (planner): creative approval per SSP (Trading), accounts and organisations with its contract (Platform), next Experience task.

## Recently merged

- 002 CI on every pull request (PR #3, 30 Oct). The brain job is red on an old bug; task 006 fixes it. Don't require CI to pass before merge until 006 is merged

- Handbook, contracts, tasks and agent rules (setup pull request #2)
- cursor-bridge extension: Claude starts Cursor agents on Sam's PC

## Waiting on Sam

- Business rules for the pricing model and the wallet (fee on top or inside the budget, first customer type, prices now or after pilots)
- Security decisions on 003: notice expiry after 48 hours, and locking the event-intake service (planner recommends yes to both)

- Start SSP outreach (VIOOH, JCDecaux and others): integration spec, sandbox, certification date. This sets the launch date
- Make the repo private (O-4)
- Pick the staging cloud and create the account (O-6), needed by Sprint 1
- Set a monthly usage limit in Cursor for three agents in parallel

## Blocked

None.
