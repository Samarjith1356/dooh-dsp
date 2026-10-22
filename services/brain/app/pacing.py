from __future__ import annotations

import json
import logging

import httpx
import redis

from app.config import CLICKHOUSE_HOST, CLICKHOUSE_HTTP_PORT, REDIS_URL
from app.models_view import CampaignView

log = logging.getLogger(__name__)


def spent_micros(campaign_id: int) -> int:
    sql = f"""
    SELECT sumMerge(spend_micros) AS spend
    FROM rtb.campaign_hourly
    WHERE campaign_id = {int(campaign_id)}
    LIMIT 1
    """
    try:
        url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
        resp = httpx.post(url, params={"default_format": "JSONEachRow", "max_execution_time": "5"}, content=sql, timeout=6)
        resp.raise_for_status()
        line = resp.text.strip().splitlines()
        if not line:
            return 0
        return int(float(json.loads(line[0]).get("spend") or 0))
    except Exception as exc:  # noqa: BLE001
        log.warning("pacing clickhouse failed: %s", exc)
        return 0


def write_budgets(campaigns: list[CampaignView]) -> None:
    r = redis.from_url(REDIS_URL)
    for c in campaigns:
        remaining = max(0, c.remaining_micros - spent_micros(c.id))
        r.set(c.budget_token if hasattr(c, "budget_token") else f"budget:{c.id}:remaining_micros", remaining)
        r.set(f"budget:{c.id}:remaining_micros", remaining)
