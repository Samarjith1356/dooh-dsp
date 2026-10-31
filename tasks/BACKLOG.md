# Backlog

The planner owns this list and Sam reorders it. Priorities follow D-013: P0 blocks a go-live item or money/legal correctness, P1 is needed for the 5 Feb prototype gate, P2 waits until after go-live. The live board is `handbook/STATUS.md`.

## Priority queue

Work top to bottom. A lane takes the highest item in its lane that has no unmet dependency.

| # | Item | Lane | Priority | Go-live item | Depends on | State |
|---|---|---|---|---|---|---|
| 1 | 002 CI on every pull request | Platform | P0 | protects all | - | merged |
| 2 | 003 Book spend on plays, not bids | Trading | P0 | 2 | - | in review |
| 2b | 006 Brain seeding without a database (CI green) | Trading | P0 | protects all | 002 | ready |
| 3 | 004 Advertiser App skeleton | Experience | P0 | 9 | - | in review |
| 4 | Creative approval per SSP before bidding | Trading | P0 | 3 | 003 | to write |
| 5 | Accounts, organisations, roles, audit log (contract first) | Platform | P0 | 5 | 002 | to write |
| 6 | 005 EUR across the stack (planned freeze) | Platform, others pause | P0 | 4 | 002, 003, 004 | ready |
| 7 | Wallet ledger and test-mode card/SEPA payments | Platform | P0 | 4 | accounts | to write |
| 8 | Lock down ClickHouse password, open ports, demo data | Trading / Platform | P0 | 8 | - | to write |
| 9 | Hosted staging environment (EU) | Platform | P0 | 8 | Sam's cloud account (O-6) | blocked on Sam |
| 10 | Advertiser App on real APIs: sign-up, upload, pay, launch, report | Experience | P0 | 9 | accounts, wallet | to write |
| 11 | Irish compliance gate v1: geofences, category bans, HFSS share, review queue | Trading / Platform | P0 | 6 | accounts | contract early |
| 12 | Ops Console: real login and server-side roles | Experience | P1 | 5 | accounts | to write |
| 13 | 001 KPIs from one full-window query | Platform | P1 | - | 002 | ready |
| 14 | Bidder warm-up and p99 decision time (max ~3.1ms today) | Trading | P1 | 7 | - | to write |
| 15 | Advertiser Agent v1 and Central Brain v1 | Agents | P1 | - | accounts, compliance | Sprint 4 |
| 16 | SSP adapter to the partner's spec, reconciliation, load test | Trading | P0 | 1, 2, 7 | partner spec | blocked outside code |
| 17 | Rename `services/brain` to `services/compiler` | all lanes | P2 | - | after go-live | parked (D-013) |

Platform can pick up 001 in a gap (for example while the accounts contract is being written), because it is small and already written.

## Outside the code (Sam), P0

The launch date depends on these, not on the build:

- Start talking to SSPs now (VIOOH, JCDecaux and others): we need an integration spec, a sandbox and a certification date. Item 16 can't start without them.
- Register the company and open a payment provider account (test mode is enough until UAT).
- Staging cloud account (O-6) by Sprint 1.
- Repo private (O-4).

## Sprint view

The sprints in `handbook/05-roadmap.md` still hold. The priority queue only decides what a free lane picks up next, so work can run ahead of its sprint.
