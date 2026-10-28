from __future__ import annotations

from typing import Any

import httpx

from agents.config import AGENT_LLM_MODEL, AGENT_LLM_TIMEOUT_SEC, XAI_API_KEY, XAI_BASE_URL


class LLMError(RuntimeError):
    pass


class LLMNotConfigured(LLMError):
    pass


def provider() -> dict[str, str]:
    """Grok (xAI) only. Never log the key. Never fall back to OpenAI."""
    key = (XAI_API_KEY or "").strip()
    if not key:
        return {"name": "none", "base_url": "", "key": "", "model": ""}
    model = (AGENT_LLM_MODEL or "").strip() or "grok-4.7"
    return {"name": "xai", "base_url": XAI_BASE_URL.rstrip("/"), "key": key, "model": model}


def status() -> dict[str, Any]:
    p = provider()
    return {
        "configured": p["name"] == "xai",
        "provider": p["name"] if p["name"] == "xai" else "none",
        "model": p["model"],
        "plane": "control",
    }


def complete(*, system: str, user: str, history: list[dict[str, Any]] | None = None) -> str:
    p = provider()
    if p["name"] != "xai":
        raise LLMNotConfigured(
            "No Grok key on the agents process. Set XAI_API_KEY from https://console.x.ai "
            "(Cursor chat Grok is not this key) and recreate the agents container."
        )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for item in history or []:
        role = str(item.get("role") or "")
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        if role in {"sam", "user"}:
            messages.append({"role": "user", "content": text})
        elif role in {"agent", "assistant"}:
            messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": user})
    url = f"{p['base_url']}/chat/completions"
    payload = {
        "model": p["model"],
        "messages": messages,
        "temperature": 0.3,
    }
    headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=AGENT_LLM_TIMEOUT_SEC) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMError(f"grok request failed: {exc}") from exc
    if resp.status_code >= 400:
        raise LLMError(f"grok HTTP {resp.status_code}: {resp.text[:400]}")
    body = resp.json()
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("grok unexpected payload") from exc
    if not str(text).strip():
        raise LLMError("grok empty completion")
    return str(text).strip()
