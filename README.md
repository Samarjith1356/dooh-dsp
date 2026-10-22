# DOOH DSP (UK & Ireland)

Programmatic demand-side platform for Digital Out-of-Home. Campaign AI runs **off** the bid path. The Go bidder matches OpenRTB 2.6 DOOH requests against a compiled in-memory rules snapshot.

## Golden rule

Bid path: HTTP parse → in-memory match → bid/no-bid → async log.

Never on that path: LLM/LangGraph, Postgres, ClickHouse, S3, or Brain reconciliation.

## Layout

| Path | Role |
| --- | --- |
| `apps/web` | Next.js portal (onboarding, creatives, agent chat, spend) |
| `services/campaign-api` | FastAPI, creatives, campaign state machine, LangGraph planner |
| `services/brain` | Deterministic compiler + overlap ranking + budget ticks |
| `services/bidder` | Go OpenRTB 2.6 DOOH endpoint |
| `services/ssp-simulator` | JCDecaux/VIOOH-shaped bid traffic |
| `services/ingest` | Batched ClickHouse inserts from HTTP/Kafka |
| `packages/ruleset` | Snapshot contract (proto + JSON Python/Go models) |
| `infra` | Compose: Postgres+pgvector, Redis, Redpanda, ClickHouse, MinIO |

## Run locally

```bash
cd infra
docker compose up --build
```

- Web: http://localhost:3000
- Campaign API: http://localhost:8000/docs
- Brain: http://localhost:8001/health
- Bidder: http://localhost:8081/health
- ClickHouse HTTP: http://localhost:8123

Live VIOOH is not required. Set `SSP_ADAPTER=simulator` (default) or `SSP_ADAPTER=viooh` to swap only the adapter (auth, `dooh.ext` normalize, creative IDs). The matcher is unchanged.

## MVP flow

1. Create advertiser (or use seeded **Demo Brand**).
2. Upload a creative that matches a seeded spec (e.g. 1920×1080 PNG for `ROADSIDE_LANDSCAPE`). Wrong aspect is rejected.
3. Create a campaign, ask the agent: *Run a 2-week brand awareness campaign targeting commuters in Dublin*.
4. Activate the campaign → Brain writes `rules:snapshot:{id}` to Redis and budget keys.
5. SSP simulator sends OpenRTB DOOH requests (London / Dublin, `qty.multiplier`).
6. Ingest batches events into `rtb.events`; `rtb.campaign_hourly` drives the dashboard and agent insights.

## Tests

```bash
cd services/campaign-api && pip install -r requirements.txt && pytest
cd services/brain && pip install -r requirements.txt && PYTHONPATH=../../packages/ruleset/python pytest
cd services/bidder && go test ./...
```
