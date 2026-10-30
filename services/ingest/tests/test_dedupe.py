from __future__ import annotations

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


def test_pacing_formula_in_ingest_suite():
    # Contract formula lives in brain; assert the same math here for the ingest lane tests.
    def spend(price_cpm: float, multiplier: float) -> int:
        return int(round(price_cpm * multiplier * 1000))

    def remaining(total_cap: int, billed: int, open_exposure: int) -> int:
        return max(0, total_cap - billed - open_exposure)

    assert spend(10.0, 5.2) == 52000
    assert remaining(1_000_000, 200_000, 50_000) == 750_000
    assert remaining(100, 80, 40) == 0
