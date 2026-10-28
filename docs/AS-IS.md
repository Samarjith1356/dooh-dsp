# DOOH DSP — As-Is Product Specification

**Product:** Programmatic demand-side platform for Digital Out-of-Home (DOOH) in Great Britain and Ireland, shaped after JCDecaux / VIOOH OpenRTB 2.6.

**Repository:** [https://github.com/Samarjith1356/dooh-dsp](https://github.com/Samarjith1356/dooh-dsp)  
**Default branch:** `main`  
**Document date:** 26 October 2026  
**This document describes the working tree as it exists on the developer machine, and separately what is already pushed to GitHub.**

---

## 1. Two source-of-truth states

GitHub `origin/main` is **behind** the local workspace. Anything used in recent E2E / UI / sub-1ms bidding work that is not listed in §1.2 is **not on Git** until it is committed and pushed.

### 1.1 On GitHub (`origin/main` = `90fe53b`)

Three commits, all on `main`:

| SHA | Date | Message |
| --- | --- | --- |
| `cf452e3` | 22 Oct 2026 21:41 +0100 | Add the UK/Ireland DOOH DSP MVP with an offline rules compiler and a Go OpenRTB bidder. |
| `68bc9c2` | 22 Oct 2026 21:56 +0100 | Serve creatives from local disk so Compose can start without MinIO. |
| `90fe53b` | 22 Oct 2026 22:16 +0100 | Pin TypeScript 5 so the Next.js Docker image can build. |

Pushed stack: four-layer MVP, Compose, Postgres+pgvector, Redis, Redpanda, ClickHouse, campaign-api, Brain, Go bidder, SSP simulator, ingest, Next.js portal (single page), ruleset proto/JSON, local-disk creatives, TypeScript 5 pin.

### 1.2 Local working tree, not on Git

These files exist in the workspace and are what a local `docker compose up --build` actually runs if the images are rebuilt from this tree:

- **Enterprise console:** App Router under `apps/web/app/(console)/` (Command Center, Inventory, Agent Studio, Ledger), Tailwind, shadcn-style UI, TanStack Query, Leaflet map, Recharts, client-side RBAC.
- **Campaign API ops/analytics extras:** `services/campaign-api/app/ops.py`; fleet health; KPIs; recent events; list plans.
- **Brain:** ruleset path walk so compile works inside the container; CORS `*`.
- **Bidder hot path:** fast OpenRTB scan, compact JSON marshal, cached Europe/London TZ, async ingest-only logging, `X-DSP-Decision-Us`, `/health` latency stats. Proven live ~50µs average, max well under 1ms after warmup.
- **ClickHouse:** `infra/clickhouse/users.d/default-network.xml` allows `default` from `::/0` (dev Docker only; required so ingest is not HTTP 403).
- **Compose:** campaign-api `BRAIN_URL` / `BIDDER_URL` / `INGEST_URL`; ClickHouse users.d mount.

`infra/_bad.png` and `infra/_ok.png` are leftover local screenshots, not product.

---

## 2. What this product is

A UK/Ireland DOOH DSP with a hard split:

| Layer | Name | Job |
| --- | --- | --- |
| 1 | Portal + Campaign API + Agent | Humans and LLM plan campaigns **offline** |
| 2 | Brain | Deterministic compiler: Postgres campaign/plan → Redis `RulesSnapshot` + budget keys |
| 3 | Go bidder | OpenRTB 2.6 DOOH bid/no-bid from **in-memory snapshot only** |
| 4 | Ingest + ClickHouse | Async logs, hourly rollups, dashboard and agent insights |

**Golden rule (enforced by architecture, not by a runtime guard):** the bid path is HTTP parse → in-memory match → bid/no-bid → non-blocking log. Never on that path: LLM / LangGraph, Postgres, ClickHouse, object storage, or Brain compile.

Currency is **GBP**. Prices and caps are stored as **integer micros** (1 GBP = 1_000_000 micros). Billable impressions use OpenRTB 2.6 `imp.qty.multiplier`.

Live VIOOH/JCDecaux exchange is **not connected**. The matcher is adapter-agnostic; `SSP_ADAPTER=simulator` (default) or `viooh` (stub: auth env + `dooh.ext` field names).

---

## 3. How to run (as-is)

From `infra/`:

```bash
docker compose up --build
```

| Surface | URL |
| --- | --- |
| Web console | http://localhost:3000 |
| Campaign API | http://localhost:8000 (`/docs`, `/health`) |
| Brain | http://localhost:8001 (`/health`, `POST /compile`) |
| Bidder | http://localhost:8081 (`/health`, `POST /openrtb/v2/bid`) |
| Ingest | http://localhost:8090 (`/health`, `POST /events`) |
| ClickHouse HTTP | http://localhost:8123 |
| Postgres | localhost:5432 (`dooh` / `dooh` / `dooh_dsp`) |
| Redis | localhost:6379 |
| Redpanda Kafka | localhost:19092 |

Optional: set `OPENAI_API_KEY` (and `LANGGRAPH_MODEL`, default `gpt-4o-mini`) if the LangGraph confirmation node should run. Without a key, the agent is **heuristic-only**.

Simulator QPS is **50** in Compose. It will consume the seeded campaign total cap (50e6 micros ≈ £50) quickly, after which the bidder correctly no-bids (`nbr: 2`) until Brain rewrites remaining budget.

---

## 4. Runtime topology

Compose services (`infra/docker-compose.yml`):

```
browser → web:3000
              ↓ NEXT_PUBLIC_API_URL
         campaign-api:8000 ──Postgres── Redis ── Redpanda
              │                 ▲
              │ POST /compile   │ rules:snapshot:*  budget:*:remaining_micros
              ▼                 │
           brain:8001 ──────────┘
              │ ClickHouse spend (pacing)
              ▼
           bidder:8081 ← ssp-simulator (50 QPS OpenRTB DOOH)
              │ async HTTP POST /events
              ▼
           ingest:8090 → ClickHouse rtb.events → MV rtb.campaign_hourly
```

Volumes: `postgres_data`, `clickhouse_data`, `creative_data` (`/data/creatives` on campaign-api).

MinIO is **not** in Compose. Creatives are files on disk, served at `http://localhost:8000/creatives/...`.

---

## 5. Data stores (as built)

### 5.1 Postgres 16 + pgvector (`dooh_dsp`)

Created on API startup via SQLAlchemy `init_db()` (no Alembic migrations). Tables:

| Table | Purpose |
| --- | --- |
| `advertisers` | Company, brand guidelines JSON, markets, ASA notes |
| `users` | Email, name, empty `password_hash` (no login) |
| `seats` | OpenRTB seat id per advertiser |
| `screen_specs` | JCDecaux/VIOOH-shaped format catalog |
| `creatives` | Asset URI, mime, WxH, validation status/errors, optional `ssp_asset_id` |
| `geofences` | Named bbox + geojson + H3 cell list |
| `campaigns` | State, flight, daily/total caps, currency, priority, bid CPM micros, creative_ids, geofence_ids |
| `campaign_plans` | Dayparts, venue allowlist, countries, geofences, bid, shade, goal, approved |
| `agent_threads` | JSON messages (schema exists; chat does not persist threads) |
| `agent_memories` | Text + `Vector(1536)` (schema exists; unused) |
| `insights` | Markdown insights (schema exists; list endpoint returns live CH summary + stored rows, none seeded) |

### 5.2 Redis 7

| Key | Writer | Reader |
| --- | --- | --- |
| `rules:current` | Brain | Bidder poll (500ms) |
| `rules:snapshot:{id}` | Brain (JSON blob) | Bidder |
| `rules.invalidate` pubsub | Brain | Unused by bidder (poll only) |
| `budget:{campaign_id}:remaining_micros` | Brain pacing | Bidder refresh loop 250ms |

### 5.3 Redpanda (Kafka API)

Topics used in code (created implicitly if the producer connects):

| Topic | Producer | Consumer | As-is status |
| --- | --- | --- | --- |
| `campaign.plan.updated` | campaign-api `bus.py` | Brain kafka loop | HTTP `POST /compile` nudge is the reliable path |
| `pacing.spend.tick` | (declared) | Brain | No producer in-tree |
| `rules.compiled` / `rules.invalidate` | Brain store | none | Best-effort |
| `rtb.bid_log` | ingest kafka loop expected | ingest | Bidder **does not produce** Kafka; HTTP ingest is the working log path |

### 5.4 ClickHouse 24.8 database `rtb`

`infra/clickhouse/init.sql`:

- `rtb.events` MergeTree, partition `toYYYYMM(event_date)`, ORDER BY advertiser/campaign/type/time, **TTL 13 months**.
- `rtb.campaign_hourly` AggregatingMergeTree.
- `rtb.mv_campaign_hourly` MV: count bids, sum billable imps, sum spend micros, avg CPM.
- `rtb.campaign_dim` ReplacingMergeTree (created, unused by app code).

Dev network ACL: `users.d/default-network.xml` sets default user `ip ::/0`. Without this, Docker ingest gets HTTP 403 (`HOST LOCAL` default). **Not a production setting.**

Event fields: `event_type` (`bid` / `nobid` / `win` / `pop`), SSP, country, venue, coarse grid `h3` (not true H3 from the bidder — see gaps), creative, bid request id, `price_cpm`, `qty_multiplier`, `billable_imps`, `spend_micros`, `snapshot_id`.

---

## 6. Shared contracts

### 6.1 Rules snapshot (`packages/ruleset`)

- `ruleset.proto` is the documented contract (`dooh.ruleset.v1`).
- Runtime encoding is **JSON**, not protobuf. Python dataclass `packages/ruleset/python/ruleset.py`; Go struct `services/bidder/internal/snapshot`.

Compiled campaign fields: id, advertiser, seat, priority, bid_cpm_micros, shading (min/max CPM, shade_factor, pwin_bin), daypart_bits (base64 of **21 bytes = 168 bits**, Mon–Sun×24 encoded as `dow*24+hour`), h3_cells, bbox, venue_types, creatives (WxH, mime, cdn_url, ssp_asset_id), budget_token, currency, deal_ids, countries.

Indexes `venue_index`, `h3_index`, `deal_index` are written by Brain. The Go matcher currently **scans campaigns linearly** and uses bbox + venue prefix + country + daypart + budget + creative size; it does not require those indexes for correctness.

### 6.2 OpenRTB (`packages/openrtb/openrtb.py`)

Python helper: a request is DOOH iff `dooh` is present and `site`/`app` are absent. Go bidder enforces the same (`openrtb.IsDOOH`).

---

## 7. Layer 1 — Campaign API

**Service:** FastAPI `DOOH Campaign API` 0.1.0, `services/campaign-api`, port 8000.  
CORS `*`. Startup: create creative dir, mount `/creatives`, `init_db()`, `bootstrap.seed()`.

### 7.1 HTTP operations

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/health` | `{"ok": true}` |
| GET | `/v1/ops/health` | Pings Brain, bidder, ingest `/health` (local tree) |
| POST | `/v1/advertisers` | Create advertiser + user + seat `seat-{id}` |
| GET | `/v1/advertisers` | List id, company, markets, asa_notes |
| GET | `/v1/screen-specs` | Seeded JCDecaux/VIOOH catalog |
| GET | `/v1/geofences?advertiser_id=` | Bboxes + H3 lists |
| POST | `/v1/creatives` | multipart: advertiser_id, spec_id, duration_ms, file. Validate vs spec; store on disk if valid |
| GET | `/v1/creatives?advertiser_id=` | List |
| POST | `/v1/campaigns` | Create in `draft` |
| GET | `/v1/campaigns?advertiser_id=` | List newest first |
| POST | `/v1/campaigns/{id}/state` | State machine. On `active`, copy latest plan bid/geofences and mark plan approved. Publishes `campaign.plan.updated` for active/paused/completed |
| POST | `/v1/campaigns/{id}/plans` | Insert plan; if `approved` and campaign draft → `pending_approval`; Kafka+Brain nudge if approved |
| GET | `/v1/campaigns/{id}/plans` | Last 20 plans (local tree) |
| POST | `/v1/plans/{id}/approve` | Mark approved, copy bid/geofences onto campaign, compile nudge |
| POST | `/v1/agent/chat` | Agent (see §8) |
| GET | `/v1/analytics/hourly` | ClickHouse hourly MV |
| GET | `/v1/analytics/kpis` | Aggregated bids, billable imps, spend, avg CPM, GB/IE sample imps (local tree) |
| GET | `/v1/analytics/events` | Recent `rtb.events` (local tree) |
| GET | `/v1/insights` | Live CH prose summary + stored Insight rows |

There is **no authentication**. Any caller can read/write all advertisers.

### 7.2 Campaign state machine

`services/campaign-api/app/state_machine.py`

```
draft ──► pending_approval ──► active ──► paused ──► active
  │              │                │          │
  └── completed  ├── draft        └── completed
                 └── paused                 └── draft
completed is terminal.
```

Illegal example: `draft → active` (must go through pending_approval). Brain compiles **only `state == "active"`** campaigns that have at least one valid creative.

### 7.3 Creative validation

`creative.validate_asset`:

- Size ≤ spec `max_bytes`
- Images (jpg/png/webp): exact WxH, exact aspect via gcd, codec in spec list
- Video (mp4/mov): codec allowlist; duration vs `max_duration_ms` if provided (no ffprobe — duration is the form field)
- Other extensions rejected

Valid files written to `{CREATIVE_DIR}/{advertiser_id}/{filename}` and URI `{CREATIVE_PUBLIC_URL}/{advertiser_id}/{filename}`.

### 7.4 Event bus

`bus.publish(topic, payload)`: Kafka if available, always HTTP `POST {BRAIN_URL}/compile` when topic is `campaign.plan.updated`.

---

## 8. Agent (offline planner)

**Code:** `services/campaign-api/app/agent.py`  
**Entry:** `POST /v1/agent/chat` `{ advertiser_id, campaign_id, message }`  
**UI:** Agent Studio (`/studio`)

The agent **never** sits on the bid path. It only writes `campaign_plans` (unapproved) and may move `draft → pending_approval`.

### 8.1 Intents

| User message | Behaviour |
| --- | --- |
| Starts with `performance` or contains `how is` | ClickHouse hourly summary string; no plan |
| Starts with `catalog` | Screen spec count + catalog payload; no plan |
| Anything else | Heuristic plan (+ optional LangGraph confirmation) |

### 8.2 Heuristic planner (`heuristic_plan`)

Keyword extraction from the free-text goal:

| Signal in text | Plan effect |
| --- | --- |
| dublin / ireland | country `IE` |
| london / uk / britain | country `GB` |
| else | `GB` and `IE` |
| commut / transit / underground / rail | venues `transit.rail`, `transit.rail.underground`, `transit.bus`; weekday (dow 0–4) hours 7–9 and 17–19 |
| road / billboard | `roadside`, `roadside.billboard` |
| else | roadside + transit.rail + urban.street; hours 6–22 all 7 days |
| `N-week` / `N week` | flight length N weeks (default 2) |
| Geofence names containing Dublin/London | those fence IDs; else all advertiser fences |

Fixed commercial knobs: `bid_cpm_micros = 6_500_000` (£6.50), `shade_factor = 0.85`.

ASA/CAP lexical flags if the goal contains `guarantee`, `miracle`, `cure`, `best in the world`.

If `campaign_id` is set and belongs to the advertiser, the plan is **persisted** and draft campaigns move to `pending_approval`.

### 8.3 LangGraph (optional)

If `OPENAI_API_KEY` is set, a three-node graph runs: `intake → compliance → propose`. Propose calls `ChatOpenAI` (`gpt-4o-mini` by default) with a short “is this UK/IE plan sensible?” prompt. The **numeric plan is still the heuristic seed**; the LLM does not rewrite venues/geos/CPM. Failures are swallowed and the heuristic plan is used.

`AgentThread` / `AgentMemory` / pgvector embeddings are **not wired** into `run_agent`.

### 8.4 Approval → compile

Studio “sign off” calls `POST /v1/plans/{id}/approve` then `POST http://localhost:8001/compile`. Activating a campaign from Command Center also nudges Brain via Kafka/HTTP.

---

## 9. Layer 2 — Brain (compiler)

**Service:** FastAPI `DOOH Brain` 0.1.0, port 8001.

| Method | Path |
| --- | --- |
| GET | `/health` |
| POST | `/compile` | Load active campaigns, compile, write Redis budgets, publish snapshot |
| GET | `/snapshot/{id}` | Current Redis snapshot JSON (returns current even if id mismatches) |

Background:

- Kafka consumer `campaign.plan.updated` + `pacing.spend.tick` → `compile_now()`
- Every **15s** pacing recompile (ClickHouse spend → Redis remaining)

`loader.load_active_campaigns`: `campaigns.state == 'active'`, latest **approved** plan, union of geofence bboxes/H3, only `validation_status == valid` creatives. Skip campaign if no valid creative.

`compiler.compile_snapshot`:

- Overlap rank: sort by `(-priority, id)`; compiled `priority` field becomes `1000 - rank`
- Dayparts → 168-bit mask (empty dayparts = **all hours allowed**)
- Shading min CPM = 40% of bid CPM, max = bid CPM, factor from plan, `pwin_bin = 0.45`
- Venue / H3 / deal inverted indexes

`pacing.write_budgets`: `remaining = max(0, total_cap_micros - ClickHouse sumMerge(spend_micros))`. Seeded demo cap is 50_000_000 micros.

Redis publish: `rules:snapshot:{id}`, `rules:current`, pubsub `rules.invalidate`.

---

## 10. Layer 3 — Go bidder

**Module:** `github.com/dooh-dsp/bidder` (Go 1.23, stdlib only).  
**Listen:** `:8081`. **Adapter:** `SSP_ADAPTER` `simulator` | `viooh`.

### 10.1 HTTP

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/health` | `ok`, adapter name; local tree also `bids`, `avg_decision_us`, `max_decision_us`, `last_decision_us` |
| POST | `/openrtb/v2/bid` | Bid or no-bid JSON. Header `X-DSP-Decision-Us` (local tree) |
| GET | `/nurl` | Win notice → async log `win` |
| GET | `/burl` | Billing/pop notice → async log `pop` |

### 10.2 Bid path (local tree)

1. Read body (1 MiB cap), pooled buffers.
2. Fast OpenRTB scan (`internal/openrtb/fast.go`); fallback `encoding/json`.
3. Reject if not exclusive DOOH (`nbr: 2`).
4. Adapter `Normalize` → canonical impression (venues, lat/lon, country, WxH, floor, qty, dooh id).
5. `matcher.Match` against atomic snapshot + in-memory budget cache.
6. Compact JSON response (`matcher.AppendResponse`).
7. `logasync.Log` onto a buffered channel; **one** background loop POSTs to ingest. No per-request goroutine, no Kafka dial on the hot path.

Timezone for daypart: `Europe/London` (tzdata in Docker image).

### 10.3 Match rules (in order, all must pass)

1. Snapshot present with campaigns
2. Country alias: GBR/UK → GB, IRL → IE
3. Point-in-bbox (campaign min/max lat/lon)
4. Venue: impression venue equals a campaign venue, **or** a dotted prefix of the impression venue is in the campaign set (e.g. campaign `roadside` matches `roadside.billboard`; campaign `transit.rail` does **not** match `transit.bus`)
5. Country allowlist if non-empty
6. Daypart bit for `weekday*24+hour` in London time (empty bits = allow)
7. In-memory remaining micros > 0
8. Creative exact WxH (or first creative if W=H=0)
9. Among survivors, highest `shadedCPM + priority`
10. Price = max(precomputed shaded CPM, bid floor)
11. `spend_micros = price * 1e6 * qty / 1000` (CPM × qty)

Shaded CPM is precomputed at snapshot load: `bid_cpm_micros/1e6 * shade_factor`, clamped to min/max CPM (default factor 0.85).

No-bid OpenRTB `nbr` is **2** (technical / invalid / no match). Site/app requests no-bid.

### 10.4 Snapshot poll and budget

- Redis `GET rules:current` every 500ms; on change load `rules:snapshot:{id}` and `prepare()` (sets, shade, creative-by-size).
- Budget cache refresh every 250ms from `budget:{id}:remaining_micros`. Until Redis has values, `Ensure` seeds 50e6 micros so first bids are not all no-bid.

### 10.5 Adapters

**Simulator:** maps `dooh.venuetype`, geo, first imp banner/video size, `qty.multiplier` default 1.

**VIOOH stub:** same plus optional `dooh.ext.screenid` / `venuetype`; AuthConfig mtls + `VIOOH_API_TOKEN` / TLS files from env. **No live HTTP to VIOOH.** Creative IDs prefixed `viooh-` unless `ssp_asset_id` set.

### 10.6 Latency (measured on local Compose)

After warmup with simulator traffic: **~50µs average decision**, last ~40µs, max hundreds of µs (under 1ms). This is parse+match+marshal, not laptop-to-Docker RTT.

---

## 11. Layer 4 — Ingest

FastAPI port 8090.

| Method | Path |
| --- | --- |
| POST | `/events` | Single event enqueue |
| POST | `/events/batch` | List enqueue |
| GET | `/health` | `ok`, `buffered` |

Buffer flush every 2s or at 1000 rows. Insert `rtb.events` JSONEachRow with `async_insert=1`. Kafka consumer `rtb.bid_log` is started but idle unless something produces that topic.

---

## 12. SSP simulator

Go process, 50 QPS in Compose, POST to `http://bidder:8081/openrtb/v2/bid`.

Four screens:

| ID | Name | Venues | Geo | Size | Floor | Qty |
| --- | --- | --- | --- | --- | --- | --- |
| jcd-lu-001 | London Underground Oxford Circus | transit.rail.underground, transit.rail | 51.5154, -0.1419 GB | 1080×1920 | 3.2 | 18.4 |
| jcd-rd-001 | London roadside A4 Cromwell | roadside.billboard, roadside | 51.495, -0.183 GB | 1920×1080 | 4.1 | 22.0 |
| jcd-dub-001 | Dublin O'Connell Street | roadside, urban.street | 53.3498, -6.2603 IE | 1920×1080 | 2.8 | 11.5 |
| jcd-dub-002 | Dublin Bus Connects | transit.bus, transit.rail | 53.347, -6.259 IE | 1080×1920 | 2.1 | 9.0 |

Requests set `tmax: 100`, `cur: GBP`, `test: 1`, `qty.sourcetype: 1`, vendor `viooh.com`. No `site`/`app`.

---

## 13. Web console (local tree)

**App:** Next.js 15.1.3, React 19, Tailwind 3, TanStack Query 5, Leaflet, Recharts, lucide, sonner. Docker `output: "standalone"`. TypeScript **5.7.2**.

**GitHub `main` still has** the original single `apps/web/app/page.tsx` onboarding/chat page. **Working tree deletes that** and uses route group `(console)`.

### 13.1 Shell

- Sidebar: Command Center `/`, Inventory `/inventory`, Agent Studio `/studio`, Ledger `/analytics`
- Header: advertiser select, region ALL/GB/IE, role select, theme toggle
- Env: `NEXT_PUBLIC_API_URL=http://localhost:8000`, `NEXT_PUBLIC_BRAIN_URL=http://localhost:8001`

### 13.2 Client RBAC (not server auth)

| Role | canWrite | canSeeOps |
| --- | --- | --- |
| org_admin | yes | yes |
| campaign_manager | yes | no |
| client_viewer | no | no |
| auditor | no | yes |

Write actions (activate, chat, approve, compile) hide when `!canWrite`. Fleet health strip only if `canSeeOps`. Default role `org_admin`. Switching roles is a UI control only.

### 13.3 Pages

**Command Center:** KPI strip (bids, billable imps, spend, CPM, GB/IE split), fleet health, campaign table with state badges, activate/pause (legal transitions), select campaign into workspace, Brain compile button for admin+ops.

**Inventory:** Leaflet map (Carto dark tiles) of London/Dublin geofence rectangles + spec list filterable by region/search. Not a live SSP inventory feed.

**Agent Studio:** campaign picker, chat, plan preview (markets, venues, dayparts, CPM, shade), approve → compile.

**Ledger:** Recharts spend/imps from hourly MV, live insight sentence, virtualized recent events table.

### 13.4 Workspace

Client state: `advertiserId` (defaults to first advertiser, typically seeded Demo Brand id=1), `campaignId`, region.

---

## 14. Seeded demo data (API startup)

If empty:

**Screen specs (6):**

| Publisher | format_code | Size | Country | Venues |
| --- | --- | --- | --- | --- |
| JCDecaux | LU_6SHEET | 1080×1920 | GB | underground / rail |
| JCDecaux | ROADSIDE_LANDSCAPE | 1920×1080 | GB | roadside |
| JCDecaux | LARGE_FORMAT | 3840×2160 | GB | roadside / mall |
| JCDecaux | DUBLIN_CITY_LANDSCAPE | 1920×1080 | IE | roadside / bus / street |
| VIOOH | PREMIUM_LANDSCAPE | 1920×1080 | GB | roadside / rail |
| VIOOH | DUBLIN_TRANSIT | 1080×1920 | IE | rail / bus |

**Advertiser:** Demo Brand, markets GB+IE, ASA note, user `demo@dooh.local`, seat `dooh-demo-seat`.

**Geofences:** London transport hubs bbox 51.28–51.70, -0.50–0.25; Dublin city center 53.25–53.45, -6.45–-6.05. Placeholder H3 integers (not generated from a live H3 library).

**Creatives:** 1920×1080 and 1080×1920 placeholder.png URIs (valid status, not uploaded files).

**Campaign:** “Demo UK/IE commute”, **already `active`**, 2-week flight, daily cap 5e6 micros, total cap 50e6 micros, priority 200, £6.50 CPM, both creatives, both fences.

**Plan:** approved, empty dayparts (all hours), venues roadside + transit.rail + transit.bus + urban.street, GB+IE, shade 0.85.

---

## 15. End-to-end operation (happy path)

1. Compose up; API seeds Demo Brand + active campaign; Brain compiles snapshot into Redis; bidder loads it.
2. Simulator sends DOOH bid requests; bidder matches bbox/venue/country/size/budget; returns seatbid with `adm` = creative CDN URL, nurl/burl on bidder, `cid` campaign id.
3. Bidder logs `bid` or `nobid` to ingest → ClickHouse. Spend accumulates; Brain every 15s sets remaining = cap − spend.
4. When remaining hits 0, matcher no-bids. Pause/activate or raise cap + compile to resume.
5. Operator uses Studio: “Run a 2-week brand awareness campaign targeting commuters in Dublin” → IE + transit venues + weekday commute hours + Dublin fence → pending_approval → approve → compile.
6. Command Center / Ledger read KPIs and events from ClickHouse via campaign-api.
7. Wrong-aspect creative upload returns `validation_status: rejected` and is not compiled onto the bid path.
8. OpenRTB `site` request → `nbr: 2`.

---

## 16. Tests in-tree

| Suite | What |
| --- | --- |
| `services/campaign-api/tests/test_state_machine.py` | Legal vs illegal transitions; only `active` compiles |
| `services/campaign-api/tests/test_creative.py` | Dimension/aspect reject |
| `services/brain/tests/test_compiler.py` | Snapshot compile |
| `packages/ruleset/python/test_ruleset.py` | JSON round-trip |
| `services/bidder/internal/matcher/matcher_test.go` | London roadside match; venue reject; marshal no-bid; Match bench (local) |
| `services/bidder/internal/openrtb/fast_test.go` | Fast parse of simulator JSON (local) |
| `services/bidder/cmd/bidder/main_test.go` | httptest decision &lt; 1ms after warmup; site no-bid (local) |

CI is **not** configured on GitHub (no Actions workflow in the tree).

---

## 17. Explicitly not built / known gaps

- Live VIOOH/JCDecaux mTLS bidding, deals, or asset registration
- User login, password hashing, API keys, org tenancy enforcement (RBAC is UI-only)
- Alembic/migrations; schema is `create_all` on boot
- True H3 library on the bid path (geofence stores placeholder uints; bidder `GridCell` is a lat/lon grid for logs only; matcher uses **bbox**, not H3 intersection)
- Daypart weekday convention: agent commute plan uses `dow` 0–4 as “weekdays”; Go `time.Weekday` has Sunday=0, so agent “weekday” bits do not line up with London Mon–Fri without a mapping
- Kafka bid log from bidder (HTTP ingest is the working path)
- MinIO / S3 creatives (removed so Compose can start)
- `AgentThread` / `AgentMemory` / vector recall
- Writing `insights` rows (read path exists)
- `campaign_dim` sync
- Production ClickHouse user/network lockdown
- Daily cap enforcement distinct from total remaining
- Bid shading using `pwin_bin` dynamically (factor is static from plan)
- Multi-imp / video-only matching beyond first imp WxH
- GitHub `main` does **not** include enterprise UI, ops endpoints, or sub-1ms bidder until those are committed

---

## 18. Repository layout (working tree)

```
apps/web/                    Next.js console
packages/openrtb/            Python DOOH request helper
packages/ruleset/            Proto + Python JSON snapshot
services/campaign-api/       FastAPI layer 1 + agent
services/brain/              Compiler + pacing
services/bidder/             Go OpenRTB bidder
services/ssp-simulator/      Synthetic UK/IE traffic
services/ingest/             ClickHouse writer
infra/docker-compose.yml     Full stack
infra/clickhouse/            Schema + (local) users.d
docs/AS-IS.md                This document
```

---

## 19. Git file inventory at `90fe53b`

Committed paths (complete): `.env.example`, `.gitignore`, `README.md`, `apps/web/*` (Dockerfile, single `app/page.tsx`, Next config, package.json), `infra/docker-compose.yml`, `infra/clickhouse/init.sql`, `packages/**`, all four Python/Go services as listed in `git ls-tree -r HEAD` (72 files). See `git ls-tree -r --name-only origin/main` for the canonical GitHub list.

---

*End of as-is specification. Implementation after this date should be treated as delta unless Git `main` is updated.*
