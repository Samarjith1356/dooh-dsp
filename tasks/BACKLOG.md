# Backlog

The planner owns this list and Sam reorders it. It follows the sprints in `handbook/05-roadmap.md`. The live board for the current sprint is `handbook/STATUS.md`.

## Sprint 0, Foundations (2-13 Nov 2026)

| Task | Lane | Notes |
|---|---|---|
| 002 CI on every pull request | Platform | Start now |
| 003 Book spend on plays, not bids | Trading | Start now. Security review |
| 004 Advertiser App skeleton | Experience | Start now |
| 001 KPIs from one full-window query | Platform | After 002 |
| 005 EUR and rename `brain` to `compiler` | Platform, other lanes paused | After 001-004 |

## Sprint 1, Accounts and money (16-27 Nov)

| Item | Lane | Notes |
|---|---|---|
| Accounts, organisations, roles, sessions | Platform | Contract first. Security review |
| Wallet ledger and test-mode payments | Platform | Needs a payment provider account in test mode |
| Hosted staging environment (EU) | Platform | Needs Sam's cloud account |
| Ops Console: real login and server-side roles | Experience | After accounts |
| Bidder warm-up and p99 decision time | Trading | The max decision time is ~3.1ms today |
| ClickHouse password, closed ports, demo data clean-up | Trading / Platform | Must happen before staging is public |

## Later sprints

Sprint 2: Advertiser App on real APIs. Sprint 3: compliance engine. Sprint 4: Advertiser Agent, Central Brain and creative studio. Sprint 5: SSP adapter, reconciliation and load test. These are broken into tasks at the start of each sprint, once the previous sprint shows what's real.

## Blocked outside the code

- A live SSP adapter needs an SSP's integration spec and sandbox (supply outreach)
