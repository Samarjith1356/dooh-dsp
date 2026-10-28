import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://dooh:dooh@localhost:5432/dooh_dsp")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:19092")
CREATIVE_DIR = os.getenv("CREATIVE_DIR", "data/creatives")
CREATIVE_PUBLIC_URL = os.getenv("CREATIVE_PUBLIC_URL", "http://localhost:8000/creatives")
BRAIN_URL = os.getenv("BRAIN_URL", "http://localhost:8001")
BIDDER_URL = os.getenv("BIDDER_URL", "http://localhost:8081")
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8090")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LANGGRAPH_MODEL = os.getenv("LANGGRAPH_MODEL", "gpt-4o-mini")
