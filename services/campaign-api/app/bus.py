from __future__ import annotations

import json
import logging

from app.config import BRAIN_URL, KAFKA_BROKERS

log = logging.getLogger(__name__)

_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer

        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            retries=1,
            request_timeout_ms=2000,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("kafka producer unavailable: %s", exc)
        _producer = False
    return _producer


def publish(topic: str, payload: dict) -> None:
    producer = _get_producer()
    if producer:
        try:
            producer.send(topic, payload)
            producer.flush(timeout=2)
        except Exception as exc:  # noqa: BLE001
            log.warning("kafka publish failed: %s", exc)
    else:
        log.info("kafka skip %s %s", topic, payload)
    if topic == "campaign.plan.updated":
        _nudge_brain()


def _nudge_brain() -> None:
    try:
        import httpx

        httpx.post(f"{BRAIN_URL}/compile", timeout=3.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("brain compile nudge failed: %s", exc)
