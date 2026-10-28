from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEMORY_DIR = Path(os.getenv("AGENT_MEMORY_DIR", str(ROOT / ".memory")))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:19092")
AGENT_LISTEN = os.getenv("AGENT_LISTEN", "0.0.0.0:8091")

BRAIN_URL = os.getenv("BRAIN_URL", "http://localhost:8001")
BIDDER_URL = os.getenv("BIDDER_URL", "http://localhost:8081")
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8090")
CAMPAIGN_API_URL = os.getenv("CAMPAIGN_API_URL", "http://localhost:8000")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))

BUS_CHANNEL = "agents.bus"
BUS_ERRORS = "agents.bus.errors"
BUS_HEALTH = "agents.bus.health"
KAFKA_TOPIC = "agents.events"

HEALTH_INTERVAL_SEC = float(os.getenv("AGENT_HEALTH_INTERVAL_SEC", "15"))
HTTP_TIMEOUT_SEC = float(os.getenv("AGENT_HTTP_TIMEOUT_SEC", "1.5"))

XAI_API_KEY = os.getenv("XAI_API_KEY", "")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
AGENT_LLM_MODEL = os.getenv("AGENT_LLM_MODEL", "grok-4.7")
AGENT_LLM_TIMEOUT_SEC = float(os.getenv("AGENT_LLM_TIMEOUT_SEC", "90"))
