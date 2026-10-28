from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from typing import TYPE_CHECKING

from app.config import DATABASE_URL, REDIS_URL

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

log = logging.getLogger("brain.memory")

KINDS = ("architecture", "campaign", "audit", "decision", "latency", "chat", "error", "compile")

_engine = None
_local: list[dict[str, Any]] = []
_pg_ready = False


class Chunk(dict):
    pass


def reset_for_tests() -> None:
    global _engine, _pg_ready
    _local.clear()
    _engine = None
    _pg_ready = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        from sqlalchemy import create_engine, text  # noqa: WPS433

        _engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("memory engine: %s", exc)
        _engine = None
    return _engine


def _text(sql: str):
    from sqlalchemy import text

    return text(sql)


def ensure_schema() -> bool:
    global _pg_ready
    eng = _get_engine()
    if eng is None:
        return False
    ddl = """
    CREATE TABLE IF NOT EXISTS enterprise_memory (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      source TEXT NOT NULL,
      title TEXT NOT NULL,
      body TEXT NOT NULL,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS enterprise_memory_kind_time
      ON enterprise_memory (kind, created_at DESC);
    CREATE INDEX IF NOT EXISTS enterprise_memory_fts
      ON enterprise_memory USING gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(body,'')));
    """
    try:
        with eng.begin() as conn:
            try:
                conn.execute(_text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception:  # noqa: BLE001
                pass
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(_text(s))
        _pg_ready = True
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("memory schema: %s", exc)
        _pg_ready = False
        return False


def _redis():
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1.5)
        r.ping()
        return r
    except Exception:
        return None


def remember(
    *,
    kind: str,
    source: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind = kind if kind in KINDS else "audit"
    chunk = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "source": source[:120],
        "title": (title or "")[:240],
        "body": (body or "")[:8000],
        "payload": payload or {},
        "created_at": _now(),
    }
    _local.append(chunk)
    if len(_local) > 4000:
        del _local[:-2000]
    eng = _get_engine()
    if eng is not None:
        if not _pg_ready:
            ensure_schema()
        try:
            with eng.begin() as conn:
                conn.execute(
                    _text(
                        "INSERT INTO enterprise_memory (id, kind, source, title, body, payload, created_at) "
                        "VALUES (:id, :kind, :source, :title, :body, CAST(:payload AS jsonb), CAST(:created_at AS timestamptz))"
                    ),
                    {
                        "id": chunk["id"],
                        "kind": chunk["kind"],
                        "source": chunk["source"],
                        "title": chunk["title"],
                        "body": chunk["body"],
                        "payload": json.dumps(chunk["payload"], default=str),
                        "created_at": chunk["created_at"],
                    },
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("memory pg insert: %s", exc)
    r = _redis()
    if r:
        try:
            r.lpush("memory:chunks", json.dumps(chunk, default=str))
            r.ltrim("memory:chunks", 0, 1999)
            r.set("memory:state", json.dumps(metrics(), default=str), ex=120)
            r.publish("memory.invalidate", chunk["id"])
        except Exception as exc:  # noqa: BLE001
            log.debug("memory redis: %s", exc)
    return chunk


def _hay(row: dict[str, Any]) -> str:
    return f"{row.get('title','')} {row.get('body','')} {row.get('kind','')} {row.get('source','')}".lower()


def _score(row: dict[str, Any], query: str) -> int:
    if not query:
        return 1
    hay = _hay(row)
    return sum(1 for tok in query.lower().split() if tok in hay)


def _load(limit: int = 400) -> list[dict[str, Any]]:
    eng = _get_engine()
    if eng is not None:
        if not _pg_ready:
            ensure_schema()
        try:
            with eng.connect() as conn:
                rows = conn.execute(
                    _text(
                        "SELECT id, kind, source, title, body, payload, created_at "
                        "FROM enterprise_memory ORDER BY created_at DESC LIMIT :lim"
                    ),
                    {"lim": limit},
                )
                out = []
                for r in rows:
                    payload = r.payload
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            payload = {}
                    created = r.created_at
                    out.append(
                        {
                            "id": r.id,
                            "kind": r.kind,
                            "source": r.source,
                            "title": r.title,
                            "body": r.body,
                            "payload": payload or {},
                            "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
                        }
                    )
                if out:
                    return out
        except Exception as exc:  # noqa: BLE001
            log.warning("memory pg read: %s", exc)
    r = _redis()
    if r:
        try:
            raw = r.lrange("memory:chunks", 0, limit - 1)
            parsed = []
            for item in raw:
                try:
                    parsed.append(json.loads(item))
                except json.JSONDecodeError:
                    continue
            if parsed:
                return parsed
        except Exception:
            pass
    return list(reversed(_local[-limit:]))


def recall(*, query: str = "", kinds: list[str] | None = None, limit: int = 12) -> list[dict[str, Any]]:
    rows = _load(800)
    if kinds:
        allow = set(kinds)
        rows = [r for r in rows if r.get("kind") in allow]
    if query.strip():
        ranked = sorted(rows, key=lambda r: _score(r, query), reverse=True)
        ranked = [r for r in ranked if _score(r, query) > 0] or ranked[:limit]
        return ranked[:limit]
    return rows[:limit]


def metrics() -> dict[str, Any]:
    rows = _load(2000)
    by_kind: dict[str, int] = {}
    for r in rows:
        k = str(r.get("kind") or "audit")
        by_kind[k] = by_kind.get(k, 0) + 1
    latest = rows[0] if rows else None
    return {
        "ok": True,
        "plane": "control",
        "chunks": len(rows),
        "by_kind": by_kind,
        "latest": latest,
        "learning": {
            "tracking": True,
            "sources": sorted({str(r.get("source") or "") for r in rows if r.get("source")}),
            "architecture_rules": by_kind.get("architecture", 0),
            "campaign_events": by_kind.get("campaign", 0),
            "audits": by_kind.get("audit", 0),
            "decisions": by_kind.get("decision", 0),
            "compiles": by_kind.get("compile", 0),
        },
    }


def seed_architecture() -> None:
    eng = _get_engine()
    if eng is not None:
        ensure_schema()
        try:
            with eng.connect() as conn:
                n = conn.execute(_text("SELECT count(*) FROM enterprise_memory WHERE kind = 'architecture'")).scalar()
                if n and int(n) > 0:
                    return
        except Exception as exc:  # noqa: BLE001
            log.debug("memory seed count: %s", exc)
    elif recall(kinds=["architecture"], limit=1):
        return
    rules = [
        (
            "Bid-path isolation",
            "Go OpenRTB bidder never calls Postgres, ClickHouse, S3, or an LLM. It matches Redis rules:snapshot compiled by Brain.",
        ),
        (
            "Daypart mapping",
            "Heuristic commute dow 0-4 is weekdays; Go time.Weekday Sunday=0. Remap before compile.",
        ),
        (
            "Billable impressions",
            "billable_imps includes qty.multiplier. Decision SLA is X-DSP-Decision-Us, not HTTP RTT.",
        ),
        (
            "HITL before live rules",
            "Product plans stay draft until approval. Brain compiles only state==active with approved plan and valid creatives.",
        ),
    ]
    for title, body in rules:
        remember(kind="architecture", source="brain.seed", title=title, body=body, payload={"immutable": True})
