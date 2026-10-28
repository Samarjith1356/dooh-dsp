# Enterprise agent workforce

Control-plane agents for https://github.com/Samarjith1356/dooh-dsp. They **do not** run on the Go bid path.

| Directory | Role |
| --- | --- |
| `architect/` | Chief Software Architect |
| `compliance/` | ASA/CAP Regulatory Guard |
| `devops/` | SRE & Infrastructure |
| `analytics/` | Data & Pacing Intelligence |
| `frontend/` | Enterprise UX & UI Control Center |
| `qa/` | Zero-Error Integration Testing |
| `product/` | Client AI Orchestrator Manager |

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

Error fingerprints live in `agents/.memory/` (gitignored) so the same failure is not retried blindly.
