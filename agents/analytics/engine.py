from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from agents.config import CLICKHOUSE_HOST, CLICKHOUSE_HTTP_PORT, HTTP_TIMEOUT_SEC, REDIS_URL

log = logging.getLogger("agents.analytics")

# Per ClickHouse agent-query-safety: timeout + row cap. Sort key prefix is advertiser_id.
QUERY_SETTINGS = "SETTINGS max_execution_time = 5, max_rows_to_read = 10000000"

SQL_CATALOG: dict[str, dict[str, str]] = {
    "hourly": {
        "rationale": (
            "Read AggregatingMergeTree via *Merge, filter ORDER BY prefix, LIMIT 168 hours. "
            "Per schema-partition-lifecycle, monthly partitions + 13-month TTL drop old data; "
            "do not DELETE FROM rtb.events."
        ),
        "sql": """
SELECT
  advertiser_id, campaign_id, hour, event_type,
  countMerge(bids) AS bids,
  sumMerge(imps) AS imps,
  sumMerge(spend_micros) AS spend_micros
FROM rtb.campaign_hourly
WHERE advertiser_id = {advertiser_id}
{campaign_pred}
GROUP BY advertiser_id, campaign_id, hour, event_type
ORDER BY hour DESC
LIMIT 168
""",
    },
    "integrity": {
        "rationale": (
            "Cross-check fact table vs hourly MV on bid rows only. "
            "billable_imps already includes qty.multiplier (sumState in MV). "
            "Lag of a few micros is ingest/async_insert, not a bidder error."
        ),
        "sql": """
SELECT
  (SELECT ifNull(sum(billable_imps), 0) FROM rtb.events
   WHERE advertiser_id = {advertiser_id} AND event_type = 'bid' {campaign_and}) AS events_imps,
  (SELECT ifNull(sum(spend_micros), 0) FROM rtb.events
   WHERE advertiser_id = {advertiser_id} AND event_type = 'bid' {campaign_and}) AS events_spend,
  (SELECT ifNull(sumMerge(imps), 0) FROM rtb.campaign_hourly
   WHERE advertiser_id = {advertiser_id} AND event_type = 'bid' {campaign_and}) AS hourly_imps,
  (SELECT ifNull(sumMerge(spend_micros), 0) FROM rtb.campaign_hourly
   WHERE advertiser_id = {advertiser_id} AND event_type = 'bid' {campaign_and}) AS hourly_spend
""",
    },
}


class Kpis(BaseModel):
    bids: float = 0
    billable_imps: float = 0
    spend_micros: int = 0
    spend_gbp: float = 0
    avg_cpm: float = 0
    gb_imps: float = 0
    ie_imps: float = 0
    hours: int = 0
    remaining_micros: int | None = None
    paced_out: bool = False


class Integrity(BaseModel):
    ok: bool = True
    events_imps: float = 0
    hourly_imps: float = 0
    events_spend: int = 0
    hourly_spend: int = 0
    imps_delta: float = 0
    spend_delta: int = 0
    note: str = ""


class InsightPack(BaseModel):
    advertiser_id: int
    campaign_id: int | None = None
    kpis: Kpis
    integrity: Integrity
    insight: str
    sql: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    ch_ok: bool = True
    error: str = ""


def avg_cpm_gbp(spend_micros: float, billable_imps: float) -> float:
    """CPM from spend micros and qty-inclusive billable imps. Never multiply qty again."""
    if billable_imps <= 0:
        return 0.0
    return round((spend_micros / 1_000_000.0) / billable_imps * 1000.0, 4)


def remaining_micros(cap: int, spend: int) -> int:
    return max(0, int(cap) - int(spend))


def insight_text(k: Kpis, paced_note: str = "") -> str:
    if k.billable_imps <= 0 and k.bids <= 0:
        return (
            "No bid or impression data yet. Activate a campaign and let the SSP simulator "
            "(or live exchange) fill rtb.events. Billable imps will already include qty.multiplier."
        )
    parts = [
        f"Recorded {k.billable_imps:.1f} billable impressions (qty.multiplier already applied) "
        f"from {k.bids:.0f} bids across {k.hours} hour bucket(s).",
        f"Spend is £{k.spend_gbp:.2f} ({k.spend_micros} micros) at £{k.avg_cpm:.2f} average CPM.",
        f"GB screens delivered {k.gb_imps:.1f} imps; Ireland {k.ie_imps:.1f}.",
    ]
    if k.paced_out:
        parts.append(
            "Remaining budget is 0 micros — bidder no-bid (nbr 2) is correct pacing, not an outage."
        )
    elif k.remaining_micros is not None:
        parts.append(f"Redis remaining budget is {k.remaining_micros} micros.")
    if paced_note:
        parts.append(paced_note)
    return " ".join(parts)


def _sql(template: str, advertiser_id: int, campaign_id: int | None) -> str:
    aid = int(advertiser_id)
    if campaign_id is not None:
        cid = int(campaign_id)
        camp_pred = f"AND campaign_id = {cid}"
        camp_and = f"AND campaign_id = {cid}"
    else:
        camp_pred = ""
        camp_and = ""
    return (
        template.format(advertiser_id=aid, campaign_pred=camp_pred, campaign_and=camp_and)
        + "\n"
        + QUERY_SETTINGS
    )


def query(sql: str) -> list[dict[str, Any]]:
    url = f"http://{CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/"
    params = {"default_format": "JSONEachRow"}
    try:
        with httpx.Client(timeout=max(6.0, HTTP_TIMEOUT_SEC)) as client:
            resp = client.post(url, params=params, content=sql.encode("utf-8"))
            resp.raise_for_status()
        rows: list[dict[str, Any]] = []
        for line in resp.text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows[:500]
    except Exception as exc:  # noqa: BLE001
        log.warning("clickhouse query failed: %s", exc)
        raise


def _redis_remaining(campaign_id: int) -> int | None:
    try:
        import redis

        r = redis.from_url(REDIS_URL, socket_timeout=1.0, decode_responses=True)
        val = r.get(f"budget:{int(campaign_id)}:remaining_micros")
        if val is None:
            return None
        return int(float(val))
    except Exception:  # noqa: BLE001
        return None


def kpis_from_hourly(rows: list[dict[str, Any]], sample: list[dict[str, Any]] | None = None) -> Kpis:
    bid_rows = [r for r in rows if r.get("event_type") == "bid"]
    bids = sum(float(r.get("bids") or 0) for r in bid_rows)
    imps = sum(float(r.get("imps") or 0) for r in bid_rows)
    spend = int(sum(float(r.get("spend_micros") or 0) for r in bid_rows))
    sample = sample or []
    gb = sum(float(r.get("billable_imps") or 0) for r in sample if r.get("country") in ("GB", "GBR"))
    ie = sum(float(r.get("billable_imps") or 0) for r in sample if r.get("country") in ("IE", "IRL"))
    return Kpis(
        bids=bids,
        billable_imps=imps,
        spend_micros=spend,
        spend_gbp=round(spend / 1_000_000.0, 4),
        avg_cpm=avg_cpm_gbp(spend, imps),
        gb_imps=gb,
        ie_imps=ie,
        hours=len({str(r.get("hour")) for r in rows}),
    )


def integrity_from_row(row: dict[str, Any] | None) -> Integrity:
    if not row:
        return Integrity(ok=True, note="no fact/MV rows yet")
    e_imps = float(row.get("events_imps") or 0)
    h_imps = float(row.get("hourly_imps") or 0)
    e_sp = int(float(row.get("events_spend") or 0))
    h_sp = int(float(row.get("hourly_spend") or 0))
    di = abs(e_imps - h_imps)
    ds = abs(e_sp - h_sp)
    # MV merge delay: allow 1% or 1 micro
    ok = di <= max(1.0, e_imps * 0.01) and ds <= max(1, int(e_sp * 0.01) if e_sp else 1)
    note = "fact vs hourly aligned" if ok else "rollup lag or double-count — check ingest async_insert, do not change bidder"
    return Integrity(
        ok=ok,
        events_imps=e_imps,
        hourly_imps=h_imps,
        events_spend=e_sp,
        hourly_spend=h_sp,
        imps_delta=di,
        spend_delta=ds,
        note=note,
    )


def pack(advertiser_id: int, campaign_id: int | None = None, cap_micros: int | None = None) -> InsightPack:
    sqls = [
        _sql(SQL_CATALOG["hourly"]["sql"], advertiser_id, campaign_id),
        _sql(SQL_CATALOG["integrity"]["sql"], advertiser_id, campaign_id),
    ]
    alerts: list[str] = []
    try:
        hourly = query(sqls[0])
        integ_rows = query(sqls[1])
    except Exception as exc:  # noqa: BLE001
        return InsightPack(
            advertiser_id=advertiser_id,
            campaign_id=campaign_id,
            kpis=Kpis(),
            integrity=Integrity(ok=False, note=str(exc)[:240]),
            insight="ClickHouse unreachable. Coordinate with DevOps (ingest 403 / HOST LOCAL is a known fingerprint).",
            sql=sqls,
            alerts=["clickhouse_down"],
            ch_ok=False,
            error=str(exc)[:240],
        )

    sample_sql = f"""
SELECT country, billable_imps, event_type
FROM rtb.events
WHERE advertiser_id = {int(advertiser_id)} AND event_type = 'bid'
{"AND campaign_id = " + str(int(campaign_id)) if campaign_id else ""}
ORDER BY event_time DESC
LIMIT 500
{QUERY_SETTINGS}
"""
    try:
        sample = query(sample_sql)
        sqls.append(sample_sql)
    except Exception:
        sample = []

    k = kpis_from_hourly(hourly, sample)
    integ = integrity_from_row(integ_rows[0] if integ_rows else None)
    if campaign_id:
        rem = _redis_remaining(campaign_id)
        k.remaining_micros = rem
        k.paced_out = rem == 0
    elif cap_micros is not None:
        k.remaining_micros = remaining_micros(cap_micros, k.spend_micros)
        k.paced_out = k.remaining_micros == 0
    if not integ.ok:
        alerts.append("integrity_mismatch")
    if k.paced_out:
        alerts.append("paced_out")
    if k.spend_micros and k.billable_imps == 0:
        alerts.append("spend_without_imps")
    return InsightPack(
        advertiser_id=advertiser_id,
        campaign_id=campaign_id,
        kpis=k,
        integrity=integ,
        insight=insight_text(k),
        sql=sqls,
        alerts=alerts,
        ch_ok=True,
    )
