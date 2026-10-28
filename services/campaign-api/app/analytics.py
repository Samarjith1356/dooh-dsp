from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import CLICKHOUSE_HOST, CLICKHOUSE_HTTP_PORT

log = logging.getLogger(__name__)


def _query(sql: str) -> list[dict[str, Any]]:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    params = {"default_format": "JSONEachRow", "max_execution_time": "5"}
    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(url, params=params, content=sql.encode("utf-8"))
            resp.raise_for_status()
        rows = []
        for line in resp.text.splitlines():
            if line.strip():
                import json

                rows.append(json.loads(line))
        return rows[:500]
    except Exception as exc:  # noqa: BLE001
        log.warning("clickhouse query failed: %s", exc)
        return []


def campaign_hourly(advertiser_id: int, campaign_id: int | None = None) -> list[dict[str, Any]]:
    where = f"advertiser_id = {int(advertiser_id)}"
    if campaign_id:
        where += f" AND campaign_id = {int(campaign_id)}"
    sql = f"""
    SELECT
      advertiser_id,
      campaign_id,
      hour,
      event_type,
      countMerge(bids) AS bids,
      sumMerge(imps) AS imps,
      sumMerge(spend_micros) AS spend_micros
    FROM rtb.campaign_hourly
    WHERE {where}
    GROUP BY advertiser_id, campaign_id, hour, event_type
    ORDER BY hour DESC
    LIMIT 168
    """
    return _query(sql)


def recent_events(advertiser_id: int, campaign_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 500))
    where = f"advertiser_id = {int(advertiser_id)}"
    if campaign_id:
        where += f" AND campaign_id = {int(campaign_id)}"
    sql = f"""
    SELECT
      event_time,
      event_type,
      campaign_id,
      country,
      venue_type,
      creative_id,
      bid_request_id,
      price_cpm,
      qty_multiplier,
      billable_imps,
      spend_micros
    FROM rtb.events
    WHERE {where}
    ORDER BY event_time DESC
    LIMIT {lim}
    """
    return _query(sql)


def kpis(advertiser_id: int, campaign_id: int | None = None) -> dict[str, Any]:
    rows = campaign_hourly(advertiser_id, campaign_id)
    bids = sum(float(r.get("bids") or 0) for r in rows if r.get("event_type") == "bid")
    imps = sum(float(r.get("imps") or 0) for r in rows if r.get("event_type") == "bid")
    spend = sum(float(r.get("spend_micros") or 0) for r in rows if r.get("event_type") == "bid")
    sample = recent_events(advertiser_id, campaign_id, limit=500)
    gb = sum(float(r.get("billable_imps") or 0) for r in sample if r.get("country") in ("GB", "GBR"))
    ie = sum(float(r.get("billable_imps") or 0) for r in sample if r.get("country") in ("IE", "IRL"))
    avg_cpm = (spend / 1_000_000) / imps * 1000 if imps else 0
    return {
        "bids": bids,
        "billable_imps": imps,
        "spend_micros": spend,
        "avg_cpm": round(avg_cpm, 4),
        "gb_imps": gb,
        "ie_imps": ie,
        "hours": len({str(r.get("hour")) for r in rows}),
    }


def summarize_performance(advertiser_id: int, campaign_id: int | None = None) -> str:
    rows = campaign_hourly(advertiser_id, campaign_id)
    if not rows:
        return "No impression or bid data yet. Activate a campaign and run the SSP simulator."
    spend = sum(float(r.get("spend_micros") or 0) for r in rows if r.get("event_type") == "bid")
    imps = sum(float(r.get("imps") or 0) for r in rows if r.get("event_type") == "bid")
    hours = {str(r.get("hour")) for r in rows}
    return (
        f"Your campaign recorded {imps:.1f} billable impressions across {len(hours)} hours. "
        f"Estimated spend is {spend / 1_000_000:.2f} (micros/1e6). "
        "Peak delivery is typically morning commute if transit venues are targeted."
    )
