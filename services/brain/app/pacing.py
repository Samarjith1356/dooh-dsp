from __future__ import annotations

import json
import logging

import httpx
import redis

from app.config import CLICKHOUSE_HOST, CLICKHOUSE_HTTP_PORT, REDIS_URL
from app.models_view import CampaignView

log = logging.getLogger(__name__)


def spend_micros_from_price(price_cpm: float, multiplier: float) -> int:
    """Billing formula: round(price_cpm * multiplier * 1000)."""
    return int(round(float(price_cpm) * float(multiplier) * 1000.0))


def remaining_micros(total_cap: int, billed_spend: int, open_exposure: int) -> int:
    """remaining = total_cap - billed spend - open exposure, never below zero."""
    return max(0, int(total_cap) - int(billed_spend) - int(open_exposure))


def _ch_json(sql: str) -> list[dict]:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    resp = httpx.post(
        url,
        params={"default_format": "JSONEachRow", "max_execution_time": "5"},
        content=sql,
        timeout=6,
    )
    resp.raise_for_status()
    lines = [ln for ln in resp.text.strip().splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def billed_and_exposure(campaign_id: int) -> tuple[int, int]:
    """Billed spend plus open win exposure (wins in last 60 minutes without billing)."""
    cid = int(campaign_id)
    sql = f"""
    SELECT
      coalesce(sumIf(spend_micros, event_type = 'billing'), 0) AS billed,
      coalesce(
        sumIf(
          toInt64(round(price_cpm * qty_multiplier * 1000)),
          event_type = 'win'
            AND event_time >= now() - INTERVAL 60 MINUTE
            AND (bid_request_id, imp_id) NOT IN (
              SELECT bid_request_id, imp_id
              FROM rtb.events
              WHERE campaign_id = {cid}
                AND event_type = 'billing'
                AND event_time >= now() - INTERVAL 60 MINUTE
            )
        ),
        0
      ) AS open_exposure
    FROM rtb.events
    WHERE campaign_id = {cid}
    """
    try:
        rows = _ch_json(sql)
        if not rows:
            return 0, 0
        row = rows[0]
        return int(float(row.get("billed") or 0)), int(float(row.get("open_exposure") or 0))
    except Exception as exc:  # noqa: BLE001
        log.warning("pacing clickhouse failed: %s", exc)
        return 0, 0


def spent_micros(campaign_id: int) -> int:
    billed, exposure = billed_and_exposure(campaign_id)
    return billed + exposure


def write_budgets(campaigns: list[CampaignView]) -> None:
    r = redis.from_url(REDIS_URL)
    for c in campaigns:
        billed, exposure = billed_and_exposure(c.id)
        remaining = remaining_micros(c.remaining_micros, billed, exposure)
        r.set(c.budget_token if hasattr(c, "budget_token") else f"budget:{c.id}:remaining_micros", remaining)
        r.set(f"budget:{c.id}:remaining_micros", remaining)
