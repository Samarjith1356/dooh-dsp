from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from agents.config import REDIS_URL
from agents import ROSTER

log = logging.getLogger("agents.worklog")

THREAD_KEY = "desk:thread:{agent}"
CURRENT_KEY = "desk:job:current"
HISTORY_KEY = "desk:jobs:{agent}"

_local_threads: dict[str, list[dict[str, Any]]] = {}
_local_current: dict[str, dict[str, Any]] = {}
_local_history: dict[str, list[dict[str, Any]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redis():
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1.5)
        r.ping()
        return r
    except Exception as exc:  # noqa: BLE001
        log.debug("worklog redis: %s", exc)
        return None


def _plain_title(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            for key in ("objective", "summary", "title", "reason"):
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()[:180]
        except json.JSONDecodeError:
            pass
    return raw[:180]


def start_job(agent: str, title: str) -> dict[str, Any]:
    job = {
        "id": str(uuid4()),
        "agent": agent,
        "title": _plain_title(title) or "Directive",
        "status": "working",
        "progress": 8,
        "steps": [
            {"label": "Brief received", "done": True},
            {"label": "Consulting fleet + memory", "done": False},
            {"label": "Agent reply", "done": False},
            {"label": "Logged to desk history", "done": False},
        ],
        "started_at": _now(),
        "updated_at": _now(),
        "summary": "",
    }
    r = _redis()
    if r:
        r.hset(CURRENT_KEY, agent, json.dumps(job))
    else:
        _local_current[agent] = job
    return job


def update_job(agent: str, *, progress: int | None = None, step: int | None = None, summary: str = "") -> dict[str, Any] | None:
    job = current_job(agent)
    if not job:
        return None
    if progress is not None:
        job["progress"] = max(0, min(100, int(progress)))
    if step is not None:
        steps = list(job.get("steps") or [])
        for i, row in enumerate(steps):
            if i <= step:
                row["done"] = True
        job["steps"] = steps
    if summary:
        job["summary"] = summary[:800]
    job["updated_at"] = _now()
    r = _redis()
    if r:
        r.hset(CURRENT_KEY, agent, json.dumps(job))
    else:
        _local_current[agent] = job
    return job


def complete_job(agent: str, summary: str = "") -> dict[str, Any] | None:
    job = update_job(agent, progress=100, step=99, summary=summary)
    if not job:
        return None
    job["status"] = "done"
    job["progress"] = 100
    job["updated_at"] = _now()
    for row in job.get("steps") or []:
        row["done"] = True
    r = _redis()
    if r:
        r.hdel(CURRENT_KEY, agent)
        r.lpush(HISTORY_KEY.format(agent=agent), json.dumps(job))
        r.ltrim(HISTORY_KEY.format(agent=agent), 0, 39)
    else:
        _local_current.pop(agent, None)
        _local_history.setdefault(agent, []).insert(0, job)
        _local_history[agent] = _local_history[agent][:40]
    return job


def current_job(agent: str) -> dict[str, Any] | None:
    r = _redis()
    if r:
        raw = r.hget(CURRENT_KEY, agent)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return _local_current.get(agent)


def job_history(agent: str, limit: int = 12) -> list[dict[str, Any]]:
    r = _redis()
    rows: list[dict[str, Any]] = []
    if r:
        for raw in r.lrange(HISTORY_KEY.format(agent=agent), 0, limit - 1):
            try:
                rows.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return rows
    return list(_local_history.get(agent) or [])[:limit]


def append_message(agent: str, role: str, text: str, job_id: str = "") -> dict[str, Any]:
    msg = {
        "id": str(uuid4()),
        "role": role,
        "text": (text or "")[:8000],
        "at": _now(),
        "job_id": job_id,
    }
    r = _redis()
    if r:
        key = THREAD_KEY.format(agent=agent)
        r.rpush(key, json.dumps(msg))
        r.ltrim(key, -200, -1)
    else:
        _local_threads.setdefault(agent, []).append(msg)
        _local_threads[agent] = _local_threads[agent][-200:]
    return msg


def thread(agent: str) -> list[dict[str, Any]]:
    r = _redis()
    if r:
        out = []
        for raw in r.lrange(THREAD_KEY.format(agent=agent), 0, 199):
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out
    return list(_local_threads.get(agent) or [])


def thread_bundle(agent: str) -> dict[str, Any]:
    cur = current_job(agent)
    hist = job_history(agent)
    return {
        "agent": agent,
        "messages": thread(agent),
        "current": cur,
        "history": hist,
        "status": "WORKING" if cur and cur.get("status") == "working" else "IDLE",
    }


def all_agent_cards() -> list[dict[str, Any]]:
    cards = []
    for name in ROSTER:
        cur = current_job(name)
        hist = job_history(name, limit=1)
        latest = cur or (hist[0] if hist else None)
        title = ""
        if latest:
            title = str(latest.get("title") or latest.get("summary") or "")
        cards.append(
            {
                "id": name,
                "status": "WORKING" if cur and cur.get("status") == "working" else "IDLE",
                "lastAction": title[:180],
                "lastActionAt": str((latest or {}).get("updated_at") or (latest or {}).get("started_at") or ""),
                "attention": "",
                "progress": int((cur or {}).get("progress") or (100 if hist else 0)),
                "job": cur,
                "recent_jobs": hist[:3],
            }
        )
    return cards


IDLE_AFTER_SEC = 20 * 60


def _age_sec(iso: str) -> float:
    try:
        started = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - started).total_seconds()
    except ValueError:
        return 0


def maybe_idle(agent: str) -> None:
    job = current_job(agent)
    if not job or job.get("status") != "working":
        return
    stamp = str(job.get("updated_at") or job.get("started_at") or "")
    if _age_sec(stamp) >= IDLE_AFTER_SEC:
        complete_job(agent, job.get("summary") or "Returned to idle after 20 minutes quiet")


def maybe_idle_all() -> None:
    for name in ROSTER:
        maybe_idle(name)


def is_idle_command(text: str) -> bool:
    return (text or "").strip().lower() in {"idle", "stop", "done", "that's all", "thats all", "finished"}


def begin_turn(agent: str, objective: str) -> dict[str, Any]:
    maybe_idle(agent)
    text = (objective or "").strip()
    if is_idle_command(text):
        job = current_job(agent)
        if job:
            complete_job(agent, "Sam marked this job idle")
            append_message(agent, "sam", text, str(job.get("id") or ""))
            append_message(agent, "agent", "Back to idle. This job is in history; open chat to read it.", str(job.get("id") or ""))
        return {"id": "", "title": "Idle", "status": "idle"}
    job = current_job(agent)
    if not job or job.get("status") != "working":
        job = start_job(agent, text)
    append_message(agent, "sam", text, str(job.get("id") or ""))
    update_job(agent, progress=max(int(job.get("progress") or 0), 35), step=1)
    return current_job(agent) or job


def finish_turn(agent: str, reply: str) -> dict[str, Any] | None:
    job = current_job(agent)
    if not job:
        return None
    append_message(agent, "agent", reply, str(job.get("id") or ""))
    progressed = min(90, max(int(job.get("progress") or 0), 70) + 8)
    return update_job(agent, progress=progressed, step=2, summary=reply[:400])
