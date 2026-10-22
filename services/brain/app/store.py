from __future__ import annotations

import json

import redis

from app.config import REDIS_URL, KAFKA_BROKERS
from app.compiler import snapshot_json
from ruleset import RulesSnapshot


def publish_snapshot(snapshot: RulesSnapshot) -> None:
    r = redis.from_url(REDIS_URL)
    blob = snapshot_json(snapshot)
    key = f"rules:snapshot:{snapshot.snapshot_id}"
    r.set(key, blob)
    r.set("rules:current", str(snapshot.snapshot_id))
    r.publish("rules.invalidate", str(snapshot.snapshot_id))
    _kafka("rules.compiled", {"snapshot_id": snapshot.snapshot_id})
    _kafka("rules.invalidate", {"snapshot_id": snapshot.snapshot_id})


def current_snapshot() -> dict | None:
    r = redis.from_url(REDIS_URL)
    sid = r.get("rules:current")
    if not sid:
        return None
    raw = r.get(f"rules:snapshot:{sid.decode() if isinstance(sid, bytes) else sid}")
    if not raw:
        return None
    return json.loads(raw)


def _kafka(topic: str, payload: dict) -> None:
    try:
        from kafka import KafkaProducer

        p = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=2000,
        )
        p.send(topic, payload)
        p.flush(2)
        p.close()
    except Exception:
        pass
