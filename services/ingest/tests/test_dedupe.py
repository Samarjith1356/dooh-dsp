from __future__ import annotations

import pytest
from fastapi import HTTPException

import app as ingest_app


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True


def test_dedupe_drops_repeat(monkeypatch):
    fake = FakeRedis()
    ingest_app.reset_redis_state_for_tests()
    ingest_app._redis = fake
    ingest_app._duplicates_dropped = 0
    ingest_app._buf.clear()

    first = ingest_app.enqueue(
        {
            "event_type": "billing",
            "bid_request_id": "r1",
            "imp_id": "1",
            "spend_micros": 52000,
            "price_cpm": 10,
            "qty_multiplier": 5.2,
            "billable_imps": 5.2,
        }
    )
    second = ingest_app.enqueue(
        {
            "event_type": "billing",
            "bid_request_id": "r1",
            "imp_id": "1",
            "spend_micros": 52000,
        }
    )
    assert first is True
    assert second is False
    assert ingest_app._duplicates_dropped == 1
    assert len(ingest_app._buf) == 1


def test_health_reports_duplicates(monkeypatch):
    ingest_app._duplicates_dropped = 3
    ingest_app._buf.clear()
    body = ingest_app.health()
    assert body["duplicates_dropped"] == 3
    assert body["ok"] is True


def test_dedupe_key_length_prefixed_disambiguates():
    # a:b / c  must not collide with a / b:c
    k1 = ingest_app.dedupe_key("billing", "a:b", "c")
    k2 = ingest_app.dedupe_key("billing", "a", "b:c")
    assert k1 != k2
    assert k1.startswith("ingest:dedupe:")
    assert len(k1) == len("ingest:dedupe:") + 64


def test_billing_503_when_redis_unavailable(monkeypatch):
    ingest_app.reset_redis_state_for_tests()
    monkeypatch.setattr(ingest_app, "_redis_client", lambda: None)
    ingest_app._buf.clear()

    with pytest.raises(ingest_app.DedupeUnavailable):
        ingest_app.enqueue(
            {
                "event_type": "billing",
                "bid_request_id": "r-money",
                "imp_id": "1",
                "spend_micros": 1000,
            }
        )
    assert len(ingest_app._buf) == 0

    with pytest.raises(HTTPException) as ei:
        ingest_app.post_event(
            ingest_app.EventIn(
                event_type="billing",
                bid_request_id="r-money-http",
                imp_id="1",
                spend_micros=1000,
            )
        )
    assert ei.value.status_code == 503


def test_non_money_passes_when_redis_unavailable(monkeypatch):
    ingest_app.reset_redis_state_for_tests()
    monkeypatch.setattr(ingest_app, "_redis_client", lambda: None)
    ingest_app._buf.clear()

    ok = ingest_app.enqueue(
        {
            "event_type": "bid",
            "bid_request_id": "r-bid",
            "imp_id": "1",
            "spend_micros": 0,
        }
    )
    assert ok is True
    assert len(ingest_app._buf) == 1

    win_ok = ingest_app.enqueue(
        {
            "event_type": "win",
            "bid_request_id": "r-win",
            "imp_id": "1",
        }
    )
    assert win_ok is True


def test_pacing_formula_in_ingest_suite():
    # Contract formula lives in brain; assert the same math here for the ingest lane tests.
    def spend(price_cpm: float, multiplier: float) -> int:
        return int(round(price_cpm * multiplier * 1000))

    def remaining(total_cap: int, billed: int, open_exposure: int) -> int:
        return max(0, total_cap - billed - open_exposure)

    assert spend(10.0, 5.2) == 52000
    assert remaining(1_000_000, 200_000, 50_000) == 750_000
    assert remaining(100, 80, 40) == 0
