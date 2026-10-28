from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from agents.config import BUS_CHANNEL, BUS_ERRORS, BUS_HEALTH, KAFKA_BROKERS, KAFKA_TOPIC, REDIS_URL
from agents.models import BusMessage

log = logging.getLogger("agents.bus")


class AgentBus:
    """Redis pub/sub with best-effort Kafka mirror. Control plane only."""

    def __init__(self) -> None:
        self._redis = None
        self._kafka = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _client(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis

            self._redis = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2.0)
            self._redis.ping()
        except Exception as exc:  # noqa: BLE001
            log.warning("redis bus unavailable: %s", exc)
            self._redis = False
        return self._redis

    def publish(self, msg: BusMessage) -> None:
        payload = msg.model_dump(mode="json")
        raw = json.dumps(payload, default=str)
        client = self._client()
        channel = BUS_CHANNEL if msg.to_agent in {"*", "orchestrator"} else f"{BUS_CHANNEL}.{msg.to_agent}"
        if client:
            try:
                client.publish(channel, raw)
                client.publish(BUS_CHANNEL, raw)
                if msg.kind == "error":
                    client.publish(BUS_ERRORS, raw)
                    client.lpush("agents:errors", raw)
                    client.ltrim("agents:errors", 0, 199)
                if msg.kind == "health":
                    client.publish(BUS_HEALTH, raw)
                    client.set("agents:health:latest", raw)
            except Exception as exc:  # noqa: BLE001
                log.warning("redis publish failed: %s", exc)
        self._kafka_send(payload)

    def _kafka_send(self, payload: dict[str, Any]) -> None:
        try:
            from kafka import KafkaProducer

            if self._kafka is None:
                self._kafka = KafkaProducer(
                    bootstrap_servers=KAFKA_BROKERS.split(","),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    request_timeout_ms=1500,
                    retries=0,
                )
            if self._kafka:
                self._kafka.send(KAFKA_TOPIC, payload)
        except Exception as exc:  # noqa: BLE001
            log.debug("kafka mirror skip: %s", exc)

    def subscribe(self, handler: Callable[[BusMessage], None], channels: list[str] | None = None) -> None:
        def loop() -> None:
            while not self._stop.is_set():
                client = self._client()
                if not client:
                    self._stop.wait(3)
                    self._redis = None
                    continue
                try:
                    pubsub = client.pubsub(ignore_subscribe_messages=True)
                    names = channels or [BUS_CHANNEL, BUS_ERRORS, BUS_HEALTH]
                    pubsub.subscribe(*names)
                    for item in pubsub.listen():
                        if self._stop.is_set():
                            break
                        if item.get("type") != "message":
                            continue
                        try:
                            msg = BusMessage.model_validate_json(item["data"])
                        except Exception:
                            continue
                        handler(msg)
                except Exception as exc:  # noqa: BLE001
                    log.warning("bus listen: %s", exc)
                    self._redis = None
                    self._stop.wait(2)

        self._thread = threading.Thread(target=loop, name="agent-bus", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
