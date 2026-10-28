# Enterprise agent workforce

Control-plane agents for https://github.com/Samarjith1356/dooh-dsp. They **do not** run on the Go bid path.

| Directory | Role |
| --- | --- |
| `architect/` | Chief Software Architect |
| `compliance/` | AdTech Compliance & Regulatory Agent (ASA/CAP, ASAI, HFSS, alcohol, political) |
| `devops/` | Site Reliability & Infrastructure (zero-trust, Redis sync, bid-path isolation) |
| `analytics/` | Data & Analytics Intelligence (ClickHouse rollups, pacing, dashboard insights) |
| `frontend/` | Frontend & Enterprise UX (control center, RBAC honesty, HITL studio) |
| `qa/` | QA & Automated Integration Testing (Zero-Error Guardian) |
| `product/` | Product & Client Campaign Agent (Client AI Orchestrator Manager) |

Each agent has `prompt.md` (system instructions) and `agent_runner.py` (FastAPI/Pydantic wrapper). `orchestrator.py` mounts all routers and subscribes to Redis pub/sub (`agents.bus`, `agents.bus.{name}`, `agents.bus.errors`, `agents.bus.health`), mirroring events to Kafka topic `agents.events` when brokers are up.

## Run

```bash
pip install -r agents/requirements.txt
# from repo root so `import agents` resolves
python -m agents.orchestrator
```

- Health: http://localhost:8091/health
- Dispatch: `POST /v1/agents/dispatch`
- Per agent: `POST /v1/agents/{name}/task`, `POST /v1/agents/{name}/errors`, `GET /v1/agents/{name}/prompt`
- Compliance audit: `POST /v1/agents/compliance/audit` → `APPROVED` | `REJECTED` | `REQUIRES HUMAN REVIEW`
- Compliance QA vectors: `GET /v1/agents/compliance/vectors`
- Publisher breach fingerprint: `POST /v1/agents/compliance/breach`
- DevOps audit: `POST /v1/agents/devops/audit?live=true` → `HEALTHY` | `DEGRADED` | `HARDENING_REQUIRED`
- Prod ClickHouse ACL: `GET /v1/agents/devops/policies/clickhouse`
- Chaos playbook (not executed): `GET /v1/agents/devops/chaos`
- Analytics insights: `GET /v1/agents/analytics/insights?advertiser_id=1`
- Analytics SQL catalog: `GET /v1/agents/analytics/sql`
- Analytics integrity: `POST /v1/agents/analytics/integrity?advertiser_id=1`
- Frontend UX audit: `POST /v1/agents/frontend/audit` → `HEALTHY` | `DEGRADED` | `BLOCKED`
- Frontend checklist: `GET /v1/agents/frontend/checklist`
- QA suite: `POST /v1/agents/qa/suite` → `GREEN` | `RED`
- QA catalog: `GET /v1/agents/qa/catalog`
- QA OpenRTB vectors: `GET /v1/agents/qa/openrtb`
- Product parse: `POST /v1/agents/product/parse` `{ "message": "…", "advertiser_id": 1 }``

Error fingerprints live in `agents/.memory/` (gitignored) so the same failure is not retried blindly.
