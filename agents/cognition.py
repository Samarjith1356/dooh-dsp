from __future__ import annotations

import logging
from typing import Any

import httpx

from agents.config import BRAIN_URL, HTTP_TIMEOUT_SEC

log = logging.getLogger("agents.cognition")


def remember(*, kind: str, source: str, title: str, body: str, payload: dict[str, Any] | None = None) -> None:
    try:
        with httpx.Client(timeout=max(HTTP_TIMEOUT_SEC, 2.0)) as client:
            client.post(
                f"{BRAIN_URL}/v1/memory",
                json={
                    "kind": kind,
                    "source": source,
                    "title": title[:240],
                    "body": (body or "")[:4000],
                    "payload": payload or {},
                },
            )
    except Exception as exc:  # noqa: BLE001
        log.debug("memory write skip: %s", exc)


def recall(query: str = "", kinds: list[str] | None = None, limit: int = 8) -> list[dict[str, Any]]:
    try:
        params: dict[str, Any] = {"q": query, "limit": limit}
        if kinds:
            params["kind"] = kinds[0]
        with httpx.Client(timeout=max(HTTP_TIMEOUT_SEC, 2.0)) as client:
            resp = client.get(f"{BRAIN_URL}/v1/memory", params=params)
            resp.raise_for_status()
            return list(resp.json().get("items") or [])
    except Exception as exc:  # noqa: BLE001
        log.debug("memory read skip: %s", exc)
        return []


def state() -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=max(HTTP_TIMEOUT_SEC, 2.0)) as client:
            resp = client.get(f"{BRAIN_URL}/v1/memory/state")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        log.debug("memory state skip: %s", exc)
        return None


def notes_for(objective: str, limit: int = 6) -> str:
    items = recall(objective, limit=limit)
    if not items:
        return ""
    lines = []
    for it in items:
        lines.append(f"- [{it.get('kind')}] {it.get('title')}: {str(it.get('body') or '')[:220]}")
    return "Enterprise memory (Brain):\n" + "\n".join(lines)
