import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://dooh:dooh@localhost:5432/dooh_dsp")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:19092")
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_HTTP_PORT = int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123"))
BIDDER_URL = os.getenv("BIDDER_URL", "http://localhost:8081")
INGEST_URL = os.getenv("INGEST_URL", "http://localhost:8090")
