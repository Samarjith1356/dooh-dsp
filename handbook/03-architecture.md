# Architecture

## What runs today

| Path | What it is | Lane | State (30 Oct 2026) |
|---|---|---|---|
| `services/bidder` | Go OpenRTB 2.6 DOOH bidder, in-memory matching, ~41µs average decision | Trading | Built. Notices don't book spend yet (task 003) |
| `services/ssp-simulator` | Sends VIOOH-shaped bid requests for 4 London/Dublin screens | Trading | Built. No auction outcomes yet (task 003) |
| `services/brain` | Rules compiler: Postgres -> Redis snapshot, budget remaining. Becomes `services/compiler` in task 005 | Trading | Built |
| `services/ingest` | Batches events into ClickHouse | Trading | Built |
| `packages/ruleset` | Snapshot format shared by the compiler and the bidder | Trading | Built |
| `services/campaign-api` | FastAPI control plane: advertisers, creatives, campaigns, plans, analytics | Platform | Partial. No accounts or wallet |
| `apps/web` | Ops Console (Next.js), including Sam's Desk | Experience | Partial |
| `apps/advertiser` | Advertiser App (Next.js) | Experience | Not started (task 004) |
| `agents/` | Control-plane agents and their orchestrator, the seed of the Central Brain | Agents | Partial |
| `infra/` | Docker Compose, ClickHouse config | Platform | Local only |
| `contracts/` | Interfaces between lanes | Planner | New |

Run everything with `docker compose -f infra/docker-compose.yml up -d --build`. Ports are listed in `README.md`.

## Target design: five layers

```
Experience      Advertiser App | Ops Console | Partner API (later)
                        |  people and agents call the same APIs
Agents          Advertiser Agents | Central Brain | Enterprise agents
                        |  agents act only through these services
Business        Accounts | Campaign Manager | Compliance engine
services        Creative studio | Wallet and billing | Reports
- - - - - - - - - - - - - - bid path boundary - - - - - - - - - - - - - -
Trading         Rules compiler | Go bidder | SSP adapters | Event pipeline
Data            Postgres | Redis | ClickHouse | Object storage
```

Everything above the line can be slow, smart and human-approved. Everything below it must answer in under a millisecond.

## Design rules

1. **No agents on the bid path.** Bid path = HTTP parse -> in-memory match -> bid/no-bid -> async log. No LLM, Postgres, ClickHouse, S3 or compile calls in there.
2. **Agents use the same APIs as people.** No direct database writes. Every action is logged with who asked, which agent acted and why.
3. **Money and publishing need approval** until an agent has a track record. Customers set their own agent's spend limits.
4. **Each Advertiser Agent sees only its own account.** It talks to enterprise agents through the Central Brain and never reaches the bidder.
5. **Model-neutral.** One interface in front of every model (Claude, Grok, others), with cost caps per agent and per customer.
6. **One EU region at launch**, close to the SSP's endpoints. Containers, with the bidder scaled horizontally.
7. **Standards first.** OpenRTB 2.6 for trading now. An agent-buying interface (AdCP or IAB Tech Lab AAMP) comes later, on the Partner API.
8. **Contracts between lanes.** Anything one lane produces and another consumes is written down in `contracts/` first.

## Data stores

| Store | Holds | Who writes |
|---|---|---|
| Postgres | Accounts, campaigns, plans, creatives metadata, wallet ledger | campaign-api |
| Redis | Compiled snapshots, budget remaining, agent bus | compiler, agents |
| ClickHouse | Every trading event, hourly rollups | ingest |
| Object storage (local disk for now) | Creative files | campaign-api |
