# DOOH DSP build status

**As of:** 28 October 2026, ~17:20 UTC  
**Repo:** https://github.com/Samarjith1356/dooh-dsp (`main` at `b9fb4b0`)  
**This machine:** full four-layer stack running in Docker Compose (`infra/docker-compose.yml`). Most of the enterprise console, Sam’s Desk, specialised agents, and bidder sub-1ms work is **local and unpushed**.

Measurements below are from live HTTP on this host, not fixtures.

## Verdict

The DSP **is running**. OpenRTB bids are flowing through the Go bidder on the simulator adapter. Control-plane services (campaign-api, Brain, ingest, agents) are up. The console at `:3000` is a real Next.js app against live APIs.

It is **not production**. ClickHouse `default` still allows `ip ::/0` (required so Docker ingest is not HTTP 403). Role switching in the header is **client-only**. The last git tag/commit on origin does **not** include Sam’s Desk or the specialised agents.

## Live compose fleet

All of these were `running` when sampled:

| Service | Host port | Role | Sample |
|---|---|---|---|
| postgres (pgvector/pg16) | 5432 | campaigns, plans, advertisers | healthy |
| redis 7 | 6379 | Brain snapshots, budget remaining, agent bus | healthy |
| redpanda | 19092 / 18082 | bid/win/loss/billing events | healthy |
| clickhouse 24.8 | 8123 / 9000 | ledger / hourly MV | up (container ~5 days, last restart 36 min) |
| campaign-api | 8000 | control plane, HITL agent, ops health | up |
| brain | 8001 | compile Postgres → Redis snapshot | up |
| bidder (Go) | 8081 | OpenRTB 2.6 in-memory | **107,922 bids, avg 41µs, last 125µs, max 3106µs** |
| ingest | 8090 | Kafka → ClickHouse | buffered 9 |
| ssp-simulator | (internal) | 50 QPS at bidder `/openrtb/v2/bid` | up |
| agents | 8091 | FastAPI workforce, Sam’s Desk APIs | 7 agents, fleet ok |
| web | 3000 | Next.js 15 console | up |

**Golden rule (enforced in bidder code, not this UI):** the bid path uses Redis + in-memory matcher only. It does not call Postgres, ClickHouse, S3/MinIO, or an LLM.

`X-DSP-Decision-Us` is the SLA, not curl RTT. Sampled **avg 41µs** (inside 1ms). **max 3106µs** is a real spike (warmup / GC / first compile) — over the 1000µs budget. Do not treat HTTP 6–15ms pings as decision time.

## Live ledger (advertiser 1, GET `/v1/analytics/kpis`)

- Spend: **1,620,781,945 micros (~£1,620.78)**
- Billable imps (`qty.multiplier` included): **~293,358**
- Avg shaded CPM: **£5.52**
- Ledger bids: **22,801** (ClickHouse; bidder counter is higher because it counts all adapter bids including no-bid)
- IE imps: **4,500** · GB imps: **0** on this KPI window (7 hours in the MV)

## Campaigns (advertiser 1)

| id | name | state | total_cap_micros |
|---|---|---|---|
| 5 | Dublin commute burst | active | 500e6 (raised live from the desk) |
| 4 | Dublin commute burst | draft | 50e6 |
| 3 | Dublin commute burst | active | 500e6 |
| 2 | Dublin commute burst | draft | 50e6 |
| 1 | Demo UK/IE commute | active | 500e6 |

Active + remaining Redis keys were starved at 0 until **cap-raise** ran against `POST /v1/campaigns/{id}/budget`. That mutation is real (Postgres cap + Redis `budget:{id}:remaining_micros`).

## Four layers (what is actually implemented)

1. **Campaign API + HITL agent** (`services/campaign-api`) — advertisers, creatives, geofences, campaign state machine (`draft → pending_approval → active`), LangGraph-shaped chat that emits PlanIn JSON. Compiles **never** happen from the browser; Brain listens on `campaign.plan.updated`.
2. **Brain** (`services/brain`) — compiles active campaigns into Redis `rules:current` / snapshot keys. Dayparts encoded as 168 bits. Budget tokens `budget:{cid}:remaining_micros`.
3. **Bidder** (`services/bidder`) — Go OpenRTB 2.6, simulator adapter (VIOOH adapter exists, not the live env). Fast JSON path, matcher isolation tests. `nbr:2` when no eligible campaign / empty remaining.
4. **Ingest + ClickHouse** — events from bidder (async), hourly MV, `billable_imps` includes `qty.multiplier`.

## Console (local, unpushed)

Routes: `/` Command Center, `/inventory`, `/studio`, `/analytics` Ledger, `/sams-desk`.

Honest limits:

- Header role dropdown is **not** server RBAC.
- Direct chat talks to `:8091` only. If the orchestrator is down, the UI **does not** fake a reply.
- Approval queue only lists **live Redis-backed findings that block soak** (starved `remaining_micros=0`). ClickHouse `::/0` and daypart homework are **not** shown as executive blockers — they are expected for this Compose file.
- Agent cards no longer show invented accuracy % or staged last-actions.

## Agents workforce

Orchestrator: `python -m agents.orchestrator` in Docker, `GET /health`, `POST /v1/agents/dispatch`, `GET /v1/desk`, `POST /v1/desk/approvals/{id}/decide`.

Roster: architect, compliance, devops, analytics, frontend, qa, product. They audit/dispatch on the **control plane**. They are not on the bid path.

Pushed to GitHub: the original `feat(agents)` commit (`b9fb4b0`). Specialised scanners, Sam’s Desk, desk approvals: **local**.

## What is still unfinished / unsafe for a real SSP

- ClickHouse default user `::/0` (dev-only; locking it without RFC1918 + Docker DNS will 403 ingest).
- No ClickHouse password; host ports 5432/6379/8123/9000 published.
- Bidder `max_decision_us` 3106µs after warmup needs a hard look if you care about p99 < 1ms.
- Duplicate seed campaigns named “Dublin commute burst”.
- KPI GB=0 while IE has imps — check geo on the simulator payload vs campaign countries.
- VIOOH/JCDecaux adapter not the live traffic source (simulator QPS=50).
- No server sessions / org tenancy.
- Origin `main` is missing most of this UI until you commit and push.

## How to run what you have

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Then: console http://localhost:3000 · OpenRTB http://localhost:8081/openrtb/v2/bid · agents http://localhost:8091/health · SLA on response header `X-DSP-Decision-Us`.
