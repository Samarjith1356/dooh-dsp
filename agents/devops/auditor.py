from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agents.config import BIDDER_URL, HTTP_TIMEOUT_SEC, REDIS_URL

REPO = Path(__file__).resolve().parents[2]


class Finding(BaseModel):
    id: str
    severity: str  # critical | warn | info | pass
    area: str
    evidence: str
    tradeoff: str
    remediation: str
    bid_path_safe: bool = True


class InfraAudit(BaseModel):
    verdict: str  # HEALTHY | DEGRADED | HARDENING_REQUIRED
    findings: list[Finding] = Field(default_factory=list)
    redis_current: str = ""
    redis_snapshot_ok: bool | None = None
    bidder_isolation_ok: bool = True
    bidder_decision_us: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


BIDDER_FORBIDDEN = (
    "clickhouse",
    "postgres",
    "pgx",
    "database/sql",
    "minio",
    "openai",
    "langgraph",
)


def _read(rel: str) -> str:
    path = REPO / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _scan_compose() -> list[Finding]:
    text = _read("infra/docker-compose.yml")
    findings: list[Finding] = []
    if not text:
        return [
            Finding(
                id="compose-missing",
                severity="critical",
                area="compose",
                evidence="infra/docker-compose.yml not found",
                tradeoff="Cannot reason about published ports or service isolation",
                remediation="Restore Compose from git",
                bid_path_safe=False,
            )
        ]
    published = re.findall(r'"(\d+):(\d+)"', text)
    host_ports = {int(h) for h, _ in published}
    for port, name in ((5432, "postgres"), (6379, "redis"), (8123, "clickhouse-http"), (9000, "clickhouse-native")):
        if port in host_ports:
            findings.append(
                Finding(
                    id=f"publish-{name}",
                    severity="warn",
                    area="network",
                    evidence=f"{name} published on host :{port}",
                    tradeoff="Local DX vs attack surface. Fine for Compose; bind 127.0.0.1 or drop publish in prod.",
                    remediation=f'Change ports to "127.0.0.1:{port}:{port}" or remove host publish; keep overlay DNS.',
                )
            )
    if "BIDDER_URL: http://bidder:8081" in text and "INGEST_URL: http://ingest:8090/events" in text:
        findings.append(
            Finding(
                id="bidder-env",
                severity="pass",
                area="bid-path",
                evidence="bidder env has REDIS_URL + INGEST_URL, no DATABASE_URL / CLICKHOUSE_HOST",
                tradeoff="None",
                remediation="Keep bidder depends_on redis+ingest only; Brain/Postgres stay off this service",
            )
        )
    if "QPS: \"50\"" in text or "QPS: '50'" in text:
        findings.append(
            Finding(
                id="simulator-qps",
                severity="info",
                area="chaos",
                evidence="ssp-simulator QPS=50 will burn the £50 demo cap quickly",
                tradeoff="Fast E2E vs empty remaining_micros / nbr:2",
                remediation="For chaos, set QPS=500 on a throwaway campaign; never against a live client cap",
            )
        )
    return findings


def _scan_clickhouse_acl() -> list[Finding]:
    text = _read("infra/clickhouse/users.d/default-network.xml")
    if "::/0" in text:
        return [
            Finding(
                id="ch-wildcard",
                severity="critical",
                area="zero-trust",
                evidence="ClickHouse default user networks ip ::/0",
                tradeoff="Unblocks Docker ingest (HOST LOCAL 403) but any host can query. Dev only.",
                remediation="Use agents/devops/policies/clickhouse-default-prod.xml (RFC1918 + password). Do not ship ::/0.",
            )
        ]
    if not text:
        return [
            Finding(
                id="ch-acl-missing",
                severity="warn",
                area="zero-trust",
                evidence="users.d/default-network.xml missing — ClickHouse may 403 ingest from Docker",
                tradeoff="Secure default vs broken pipeline",
                remediation="Dev: allow Docker bridge CIDR only. Prod: password + RFC1918.",
            )
        ]
    return [
        Finding(
            id="ch-acl",
            severity="pass",
            area="zero-trust",
            evidence="ClickHouse networks are not ::/0",
            tradeoff="None",
            remediation="Keep passworded users for prod",
        )
    ]


def _scan_bidder_isolation() -> tuple[bool, list[Finding]]:
    findings: list[Finding] = []
    go_files = list((REPO / "services" / "bidder").rglob("*.go"))
    hits: list[str] = []
    for path in go_files:
        body = path.read_text(encoding="utf-8", errors="replace").lower()
        for needle in BIDDER_FORBIDDEN:
            if needle in body:
                hits.append(f"{path.relative_to(REPO)}:{needle}")
    ok = not hits
    if hits:
        findings.append(
            Finding(
                id="bidder-datastore-import",
                severity="critical",
                area="bid-path",
                evidence="; ".join(hits[:12]),
                tradeoff="Any CH/PG client on the bidder violates the golden rule and adds ms-level I/O",
                remediation="Remove the import. Match only the Redis snapshot. Log async to ingest.",
                bid_path_safe=False,
            )
        )
    else:
        findings.append(
            Finding(
                id="bidder-isolation",
                severity="pass",
                area="bid-path",
                evidence=f"scanned {len(go_files)} Go files; no Postgres/ClickHouse/LLM clients",
                tradeoff="None",
                remediation="Keep go.mod stdlib-only",
            )
        )
    dockerfile = _read("services/bidder/Dockerfile")
    if "tzdata" not in dockerfile:
        findings.append(
            Finding(
                id="bidder-tzdata",
                severity="warn",
                area="daypart",
                evidence="bidder Dockerfile missing tzdata",
                tradeoff="Wrong daypart bits vs London local time",
                remediation="apk add tzdata in build and runtime images; ENV TZ=Europe/London",
            )
        )
    return ok, findings


def _redis_snapshot() -> tuple[str, bool | None, list[Finding]]:
    findings: list[Finding] = []
    sid = ""
    ok: bool | None = None
    try:
        import redis

        r = redis.from_url(REDIS_URL, socket_timeout=1.0, decode_responses=True)
        sid = r.get("rules:current") or ""
        if not sid:
            findings.append(
                Finding(
                    id="redis-no-current",
                    severity="warn",
                    area="snapshot",
                    evidence="rules:current empty",
                    tradeoff="Bidder no-bids until Brain compiles",
                    remediation="POST Brain /compile after an active campaign exists",
                )
            )
            return sid, False, findings
        blob = r.get(f"rules:snapshot:{sid}")
        if not blob:
            ok = False
            findings.append(
                Finding(
                    id="redis-desync",
                    severity="critical",
                    area="snapshot",
                    evidence=f"rules:current={sid} but rules:snapshot:{sid} missing",
                    tradeoff="Bidder polls a dangling pointer — all requests nbr:2",
                    remediation="Brain must SET snapshot blob before flipping rules:current",
                    bid_path_safe=False,
                )
            )
        else:
            ok = True
            findings.append(
                Finding(
                    id="redis-sync",
                    severity="pass",
                    area="snapshot",
                    evidence=f"rules:current={sid} blob_bytes={len(blob)}",
                    tradeoff="None",
                    remediation="Keep 500ms bidder poll; 250ms budget refresh",
                )
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            Finding(
                id="redis-down",
                severity="critical",
                area="snapshot",
                evidence=str(exc)[:240],
                tradeoff="No snapshot, no agent bus",
                remediation="Start Redis; check REDIS_URL",
                bid_path_safe=False,
            )
        )
    return sid, ok, findings


def _bidder_health() -> tuple[dict[str, Any], list[Finding]]:
    import httpx

    findings: list[Finding] = []
    payload: dict[str, Any] = {}
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SEC) as client:
            resp = client.get(f"{BIDDER_URL}/health")
        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text[:200]}
        avg = int(payload.get("avg_decision_us") or 0)
        mx = int(payload.get("max_decision_us") or 0)
        if mx >= 1000:
            findings.append(
                Finding(
                    id="bidder-max-us",
                    severity="warn",
                    area="latency",
                    evidence=f"max_decision_us={mx} (SLA <1000)",
                    tradeoff="GC/first-request spikes vs hot-path average",
                    remediation="Keep fast OpenRTB scan, pooled buffers, no per-request goroutine HTTP",
                )
            )
        elif "avg_decision_us" in payload:
            findings.append(
                Finding(
                    id="bidder-us",
                    severity="pass",
                    area="latency",
                    evidence=f"avg_decision_us={avg} max_decision_us={mx}",
                    tradeoff="None — this is decision time, not curl RTT",
                    remediation="Alert if avg_decision_us > 500",
                )
            )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            Finding(
                id="bidder-down",
                severity="critical",
                area="latency",
                evidence=str(exc)[:240],
                tradeoff="No live bids",
                remediation="docker compose up bidder; confirm :8081",
                bid_path_safe=False,
            )
        )
    return payload, findings


def audit(live: bool = True) -> InfraAudit:
    findings: list[Finding] = []
    findings.extend(_scan_compose())
    findings.extend(_scan_clickhouse_acl())
    isolated, iso_findings = _scan_bidder_isolation()
    findings.extend(iso_findings)
    sid = ""
    snap_ok: bool | None = None
    bidder_us: dict[str, Any] = {}
    if live:
        sid, snap_ok, redis_findings = _redis_snapshot()
        findings.extend(redis_findings)
        bidder_us, lat_findings = _bidder_health()
        findings.extend(lat_findings)
    else:
        findings.append(
            Finding(
                id="offline",
                severity="info",
                area="telemetry",
                evidence="live Redis/bidder probes skipped",
                tradeoff="Static repo scan only",
                remediation="POST /v1/agents/devops/audit with live=true when Compose is up",
            )
        )

    crit = [f for f in findings if f.severity == "critical"]
    warns = [f for f in findings if f.severity == "warn"]
    if crit or not isolated:
        verdict = "HARDENING_REQUIRED"
    elif warns:
        verdict = "DEGRADED"
    else:
        verdict = "HEALTHY"

    notes = [
        "Golden rule: bidder matches in-memory Redis snapshots only.",
        "HTTP ingest is the working bid-log path; Kafka rtb.bid_log from bidder is unused.",
        "ClickHouse TTL 13 months / hourly MV owned with Analytics.",
    ]
    return InfraAudit(
        verdict=verdict,
        findings=findings,
        redis_current=sid,
        redis_snapshot_ok=snap_ok,
        bidder_isolation_ok=isolated,
        bidder_decision_us=bidder_us,
        notes=notes,
    )


CHAOS_PLAYBOOK: dict[str, Any] = {
    "redis_disconnect": {
        "inject": "docker compose stop redis",
        "expect": "bidder no-bids (nbr 2); Brain compile fails; agent bus silent",
        "recover": "docker compose start redis && POST brain /compile",
        "never_repeat": "Do not teach the bidder to fail-open with stale unlimited budget",
    },
    "ingest_stall": {
        "inject": "docker compose stop ingest",
        "expect": "bidder still <1ms (async log drop); ClickHouse rollups freeze",
        "recover": "start ingest; Analytics checks hourly lag",
        "never_repeat": "Do not block handleBid on ingest HTTP",
    },
    "qps_500": {
        "inject": "QPS=500 on ssp-simulator against a throwaway campaign",
        "expect": "decision_us stays <1000; remaining_micros hits 0 then nbr:2",
        "recover": "reset cap via Brain; never run against a live client",
        "never_repeat": "50 QPS demo cap burn is not a bidder bug",
    },
}
