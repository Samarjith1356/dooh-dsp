# DOOH DSP — everything built so far

**Product:** Programmatic demand-side platform for Digital Out-of-Home in Great Britain and Ireland (JCDecaux / VIOOH-shaped, OpenRTB 2.6).

**Repo:** https://github.com/Samarjith1356/dooh-dsp  
**This document:** 28 October 2026. It describes the **working tree on the developer machine** (what `docker compose -f infra/docker-compose.yml up --build` actually runs after a rebuild), and separately what is on GitHub.

Related snapshots: [AS-IS.md](./AS-IS.md) (26 Oct, pre–Sam’s Desk) and [BUILD-STATUS.md](./BUILD-STATUS.md) (live metrics from 28 Oct).

---

## 1. What this is

A UK/IE DOOH DSP with a hard split between **planning** and **bidding**:

| Layer | Name | Job | On the bid path? |
| --- | --- | --- | --- |
| 1 | Console + Campaign API + HITL agent | Humans and an LLM plan campaigns, upload creatives, change state | No |
| 2 | Brain | Deterministic compiler: Postgres campaign/plan → Redis `RulesSnapshot` + budget keys | No (writes Redis; bidder only reads) |
| 3 | Go bidder | OpenRTB 2.6 DOOH bid/no-bid from an **in-memory snapshot** | **Yes — this is the bid path** |
| 4 | Ingest + ClickHouse | Async logs, hourly rollups, dashboard KPIs | No |
| Control | Agents orchestrator + Sam’s Desk | Seven specialised control-plane agents, Redis bus, live approvals | No |

**Golden rule:** bid path is HTTP parse → in-memory match → bid/no-bid → non-blocking log. Never on that path: LLM / LangGraph, Postgres, ClickHouse, object storage, or Brain compile.

**Money:** GBP, integer **micros** (1 GBP = 1_000_000 micros). Billable impressions use OpenRTB 2.6 `imp.qty.multiplier`.

**Live exchange:** VIOOH / JCDecaux is **not connected**. Traffic is the in-repo SSP simulator (`SSP_ADAPTER=simulator`). A VIOOH adapter stub exists (`dooh.ext` field names, auth env) and does not change the matcher.

---

## 2. Git vs this machine

| Where | Tip | What it contains |
| --- | --- | --- |
| GitHub `origin/main` | `b9fb4b0` | Four-layer MVP + TypeScript pin + local-disk creatives + **agents scaffold** (roster, bus, architect runtime) |
| Local working tree | uncommitted / unpushed | Enterprise console, specialised agents (compliance, devops, analytics, frontend, QA, product), Sam’s Desk, live desk approvals, bidder sub-1ms path, ClickHouse `users.d`, campaign-api ops/budget endpoints |

Until you commit and push, a clone of GitHub does **not** have Sam’s Desk or the specialised scanners.

Pushed history (oldest → newest):

1. `cf452e3` — MVP: offline rules compiler + Go OpenRTB bidder  
2. `68bc9c2` — creatives from local disk (Compose without MinIO)  
3. `90fe53b` — pin TypeScript 5 so the Next Docker image builds  
4. `b9fb4b0` — enterprise agent workforce scaffold and communication bus  

---

## 3. How to run

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

| Surface | URL | Notes |
| --- | --- | --- |
| Web console | http://localhost:3000 | Command Center, Inventory, Studio, Ledger, Sam’s Desk |
| Campaign API | http://localhost:8000 | `/docs`, `/health` |
| Brain | http://localhost:8001 | `/health`, `POST /compile` |
| Bidder | http://localhost:8081 | `/health`, `POST /openrtb/v2/bid`, `/nurl`, `/burl` |
| Ingest | http://localhost:8090 | `/health`, `POST /events` |
| Agents | http://localhost:8091 | `/health`, `/v1/desk`, `/v1/agents/dispatch` |
| ClickHouse HTTP | http://localhost:8123 | DB `rtb` |
| Postgres | localhost:5432 | `dooh` / `dooh` / `dooh_dsp` |
| Redis | localhost:6379 | snapshots, remaining budget, agent bus |
| Redpanda | localhost:19092 | Kafka-compatible events |

Decision SLA is response header **`X-DSP-Decision-Us`**, not curl RTT.

Seeded advertiser: **Demo Brand** (`demo@dooh.local`), London + Dublin geofences, roadside 1920×1080 + portrait creatives, campaign **Demo UK/IE commute**.

---

## 4. Repository layout

```
apps/web/                 Next.js 15 console (App Router, Tailwind, TanStack Query)
services/campaign-api/    FastAPI control plane
services/brain/           Python compiler → Redis
services/bidder/          Go OpenRTB 2.6
services/ssp-simulator/   50 QPS synthetic DOOH bid stream
services/ingest/          Kafka/HTTP → ClickHouse batches
packages/ruleset/         Snapshot contract (proto + Python JSON models)
packages/openrtb/         Shared OpenRTB helpers (Python)
agents/                   Control-plane workforce (FastAPI :8091)
infra/                    Compose, ClickHouse init.sql + users.d
docs/                     This file, AS-IS, BUILD-STATUS
```

---

## 5. Layer 1 — Campaign API and HITL agent

**Path:** `services/campaign-api`  
**Process:** FastAPI, SQLAlchemy, Postgres + pgvector, Redis, Kafka publish, local-disk creatives, optional LangGraph/OpenAI for `/v1/agent/chat`.

### Domain model (Postgres)

- **Advertiser** — company, markets (`GB`/`IE`), ASA notes, brand guidelines JSON  
- **User / Seat** — demo user + `dooh-demo-seat`  
- **ScreenSpec** — publisher format codes (e.g. `ROADSIDE_LANDSCAPE` 1920×1080)  
- **Geofence** — GeoJSON + H3 cells + bounding box (seeded London, Dublin)  
- **Creative** — width/height/mime/validation_status, served from `/creatives`  
- **Campaign** — state, flight, caps (daily + total micros), bid CPM micros, creative_ids, geofence_ids, priority  
- **CampaignPlan** — dayparts, venue allowlist, countries, geofences, shade_factor, goal, approved  
- **Insight** — stored markdown from analytics summaries  

### Campaign state machine

`draft → pending_approval → active → paused → completed`  
(`paused` can return to `active` or `draft`; `completed` is terminal.)

**Only `active` compiles into Redis.** Draft and pending_approval never reach the bidder.

### HTTP API (built)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness |
| POST/GET | `/v1/advertisers` | create / list |
| GET | `/v1/screen-specs` | seeded formats |
| GET | `/v1/geofences` | advertiser fences |
| POST/GET | `/v1/creatives` | multipart upload + list (aspect/size validation) |
| POST/GET | `/v1/campaigns` | create / list |
| POST | `/v1/campaigns/{id}/state` | legal transitions; `active` publishes compile |
| POST | `/v1/campaigns/{id}/plans` | PlanIn JSON |
| POST | `/v1/campaigns/{id}/budget` | set `total_cap_micros`, optionally reset Redis remaining |
| POST | `/v1/plans/{id}/dayparts` | remap dayparts + republish compile |
| POST | `/v1/plans/{id}/approve` | HITL approve |
| POST | `/v1/agent/chat` | LangGraph-shaped planner (offline; `needs_approval`) |
| GET | `/v1/campaigns/{id}/plans` | plan history |
| GET | `/v1/ops/health` | ping brain, bidder, ingest |
| GET | `/v1/analytics/hourly` | ClickHouse hourly MV |
| GET | `/v1/analytics/kpis` | spend, billable imps (qty included), CPM, GB/IE split |
| GET | `/v1/analytics/events` | recent `rtb.events` |
| GET | `/v1/insights` | live text + stored markdown |

Creatives: PNG/JPEG/WebP/MP4/MOV; reject wrong aspect vs screen spec; stored under `CREATIVE_DIR` (Compose volume), **not** MinIO (removed so Compose starts without object storage).

HITL agent (`app/agent.py`): parses a natural-language goal into a plan, runs a **lexical compliance** pass (absolute claims like “guarantee”), returns `needs_approval`. It does **not** write Redis itself.

Kafka: `campaign.plan.updated` when state becomes active/paused/completed or a plan is approved — Brain consumes and compiles.

---

## 6. Layer 2 — Brain (compiler)

**Path:** `services/brain`

- Loads **active** campaigns + latest approved plan from Postgres.  
- Encodes dayparts as **168 bits** (7×24), base64 in `daypart_bits`. Convention in Go: Sunday = 0.  
- Ranks overlapping geo/venue/daypart (higher priority, then lower id).  
- Writes Redis:
  - `rules:snapshot:{id}`
  - `rules:current` (pointer the bidder polls)
  - `budget:{campaign_id}:remaining_micros` (from `total_cap_micros` minus paced spend)
- HTTP: `GET /health`, `POST /compile` (manual recompile from the console).  
- CORS `*` for the local console.  
- **Never called from the bidder.**

Shading: `shade_factor` (default 0.85) on PlanIn; compiled into `ShadingParams` (min/max CPM, pwin bin). Bidder applies shade when pricing.

---

## 7. Layer 3 — Go bidder (the only bid path)

**Path:** `services/bidder`

### Endpoints

- `POST /openrtb/v2/bid` — OpenRTB 2.6 DOOH  
- `GET /health` — `ok`, adapter name, `bids`, `avg_decision_us`, `max_decision_us`, `last_decision_us`  
- `GET /nurl`, `GET /burl` — win/billing notices → async ingest  

Header **`X-DSP-Decision-Us`**: microseconds spent **inside** match+serialize, not network RTT.

### Hot path (built for sub-1ms)

- Fast OpenRTB scan (`internal/openrtb/fast.go`) — avoid full generic JSON where possible  
- Compact bid response marshal  
- Cached `Europe/London` timezone for daypart  
- Object pools for request/body/response buffers  
- Snapshot held in memory (`snapshot.Holder`); Redis poll is a **background** goroutine  
- Budget remaining cached in memory, refreshed from Redis off the request  
- Logs are **async HTTP** to ingest only (`internal/logasync`) — no Kafka, CH, or Postgres on the request  

### Matcher

Filters in order: snapshot present → country (GBR/UK→GB, IRL→IE) → bbox → venue types → country set → daypart bits vs London local time → remaining micros > 0 → creative WxH → score/priority → shade price.

No eligible campaign → OpenRTB **`nbr: 2`**. Empty remaining is pacing, not an outage.

### Adapters

| Name | Env | Behaviour |
| --- | --- | --- |
| `simulator` | default | Canonical lat/lon/venue/qty from simulator JSON |
| `viooh` | `SSP_ADAPTER=viooh` | Auth env + `dooh.ext` names; matcher unchanged |

Sampled on this host (28 Oct 2026): **avg ~41µs**, **max 3106µs** (warmup spike over the 1000µs budget), 100k+ adapter bids.

---

## 8. Layer 4 — Ingest and ClickHouse

**Ingest** (`services/ingest`): FastAPI; accepts POST `/events` from the bidder; also Kafka; batches into ClickHouse HTTP.

**ClickHouse** (`infra/clickhouse/init.sql`):

- `rtb.events` — MergeTree, 13-month TTL; `qty_multiplier`, `billable_imps`, `spend_micros`  
- `rtb.campaign_hourly` — AggregatingMergeTree  
- `rtb.mv_campaign_hourly` — MV from events  
- `rtb.campaign_dim` — ReplacingMergeTree names  

**Dev ACL:** `infra/clickhouse/users.d/default-network.xml` sets `default` user `ip ::/0`. That is **required** so Docker ingest is not HTTP 403 (`HOST LOCAL`). It is **not** a production ACL. A prod XML (RFC1918 + password) lives at `agents/devops/policies/clickhouse-default-prod.xml` and is **not** mounted.

KPIs from campaign-api use `sum(billable_imps)` so **qty.multiplier is in the ledger**.

---

## 9. SSP simulator

**Path:** `services/ssp-simulator`  
Compose `QPS: "50"` at `http://bidder:8081/openrtb/v2/bid`.  
Shapes JCDecaux/VIOOH-like DOOH impressions (London / Dublin, `qty.multiplier`).  
Will burn a £50 cap quickly; remaining 0 → `nbr:2` is correct.

---

## 10. Snapshot contract (`packages/ruleset`)

`ruleset.proto` + Python dataclasses (`CompiledCampaign`, `CreativeRef`, `ShadingParams`, `RulesSnapshot`). JSON encoding at runtime (no protoc in the hot path). Go bidder has a matching `internal/snapshot` struct (`DaypartBits`, bbox, venues, creatives, budget token).

---

## 11. Web console (`apps/web`)

Next.js 15 App Router, Tailwind, shadcn-style kit, TanStack Query, Leaflet, Recharts, Sonner toasts.

### Shell

- Sidebar: Command Center, Inventory, Agent Studio, Ledger, **Sam’s Desk**  
- Header: advertiser select, region (GB+IE / GB / IE), **role dropdown**, theme toggle  
- **Role is client-only** (`lib/rbac.tsx`). It hides buttons; it is **not** server tenancy. Do not call it secure RBAC.

### Pages

| Route | What it does |
| --- | --- |
| `/` Command Center | Fleet health, KPIs, campaign list, legal state buttons, `POST /compile` |
| `/inventory` | Leaflet map of geofences / specs |
| `/studio` | HITL chat + plan preview + approve (campaign-api agent) |
| `/analytics` Ledger | Hourly chart, events table, spend |
| `/sams-desk` | Executive agent command center (see §13) |

Workspace (`lib/workspace.tsx`): advertiser id, optional campaign id, region — client state.

---

## 12. Control-plane agents (`agents/`)

**Not on the bid path.** FastAPI orchestrator `:8091` in Compose (`agents/Dockerfile`).

### Roster

| id | Role | What was built |
| --- | --- | --- |
| architect | Chief Software Architect | Isolation / OpenRTB / latency contracts; prompt + runtime |
| compliance | ASA/CAP / ASAI / HFSS / alcohol / political | `scanner.py`, `rulebook.py`, audit verdicts, QA vectors, breach fingerprint |
| devops | SRE | Compose/CH ACL/bidder isolation auditor, prod CH XML, chaos playbook (not executed) |
| analytics | OLAP & pacing | ClickHouse insights, SQL catalog, integrity vs hourly MV, `qty.multiplier` |
| frontend | Enterprise UX | Route/RBAC/honesty auditor, checklist |
| qa | Zero-Error Guardian | In-process suite (state machine, isolation, OpenRTB nbr vectors), catalog |
| product | Lead deputy / client goals | `planner.py` PlanIn parse, compliance gate before approval CTA |

Each agent: `prompt.md` + `agent_runner.py`. Shared: `runtime.py` (task handle, handoffs), `bus.py` (Redis pub/sub + Kafka mirror), `memory.py` (error fingerprints in `agents/.memory/`), `state.py` (fleet ping).

### Orchestrator HTTP

- `GET /health` — roster + fleet (campaign-api, brain, bidder, ingest, Redis)  
- `POST /v1/agents/dispatch` — one agent or `*` broadcast  
- Per agent: `/v1/agents/{name}/task`, `/errors`, `/prompt` plus the specialised routes in `agents/README.md`  
- `GET /v1/desk` — live approvals + bus feed (health ticks stripped)  
- `POST /v1/desk/approvals/{id}/decide` — persist in Redis; **Approve executes** (see below)

---

## 13. Sam’s Desk

**UI:** `apps/web/app/(console)/sams-desk`  
**API:** `agents/desk.py` + Redis keys `desk:approvals`, `agents:feed`

### What the page shows (live only)

- Orchestrator liveness (`:8091`)  
- Fleet strip from `/health` (campaign-api, brain, bidder with **avg decision µs**, ingest, Redis)  
- KPI ribbon from ClickHouse via campaign-api (spend, billable imps, CPM, bids, bidder decision)  
- Seven agent cards (name, focus, **Direct chat**). No invented accuracy %. Last action only if the Redis bus has a real event  
- Direct chat: left drawer → `POST /v1/agents/dispatch`. If `:8091` is down, **no fake reply**  
- Broadcast to all seven (live dispatch only)  
- Jump palette (open chat)  
- Operations feed from Redis bus (health JSON dumps hidden)  
- Approval queue from Redis, **pending only if a live finding still exists**

Removed on purpose: mock feed, mock three-item queue, voice sim, emergency-pause toast, duplicate below-the-fold chat hub, staged “AUDITING / 99.8%” cards.

### Live approval actions that actually mutate the stack

| id | When it appears | Approve does |
| --- | --- | --- |
| `cap-raise` | Redis `budget:{id}:remaining_micros = 0` | `POST /v1/campaigns/{id}/budget` 500e6 + reset remaining |
| `ch-acl` | (endpoint exists, **not auto-queued**) | ClickHouse `ALTER USER` + write RFC1918 `users.d` |
| `daypart-map` | (endpoint exists, **not auto-queued**) | Remap commute dow 0–4 → Go Sunday=0 weekdays 1–5 |

CH `::/0` and daypart homework are **not** executive blockers for local Compose (ingest needs the open ACL). Cap-raise **was** applied live on this host for campaigns 1, 3, 5.

---

## 14. Tests that exist

| Area | How |
| --- | --- |
| Campaign API | `pytest` — state machine, creative validation |
| Brain | `pytest` — compiler / daypart encode |
| Bidder | `go test ./...` — matcher, fast JSON, main |
| Ruleset | Python `test_ruleset.py` |
| Agents | `pytest agents/tests` — runtime memory, compliance, devops, analytics, frontend, QA, product parse, desk dow remap |

---

## 15. Compose services (as-is)

postgres (pgvector), redis 7, redpanda, clickhouse 24.8, campaign-api, brain, bidder, ssp-simulator, ingest, **agents**, web.

Published host ports include 5432, 6379, 8123, 9000 — fine for local DX, not for a public network.

MinIO was dropped from the happy path; creatives are a Docker volume.

---

## 16. What is deliberately not built (or not honest yet)

- Live VIOOH / JCDecaux seat, deals, or production creative registration  
- Server-side auth, sessions, org tenancy, audit log of human users  
- ClickHouse password + RFC1918-only users **mounted** (XML exists, Compose still uses `::/0`)  
- Binding DB/Redis/CH to `127.0.0.1` only  
- Guaranteed p99 < 1ms (avg is fine; max has spiked above 1000µs)  
- Deduped demo campaigns (multiple “Dublin commute burst” rows from Studio/agent use)  
- Voice I/O, true emergency bidder freeze from the desk  
- Push of the enterprise console / specialised agents to GitHub  

---

## 17. End-to-end flow that works today

1. Console (or seed) has Demo Brand, creatives, London/Dublin fences.  
2. Studio chat or Product agent turns a goal into PlanIn JSON. Compliance can reject copy.  
3. Human moves `draft → pending_approval → active`.  
4. Brain compiles Redis snapshot + budget keys.  
5. Simulator sends OpenRTB; Go bidder matches in memory; header `X-DSP-Decision-Us`.  
6. Async ingest → ClickHouse; Ledger and Command Center KPIs update.  
7. If remaining hits 0, bidder returns `nbr:2`; Sam’s Desk can raise cap for soak.  
8. Direct chat on Sam’s Desk dispatches a named agent on `:8091` without touching the bidder.

That is the product as built.
