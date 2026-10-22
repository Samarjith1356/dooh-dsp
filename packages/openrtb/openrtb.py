"""Minimal OpenRTB 2.6 DOOH models shared by Python services."""

from __future__ import annotations

from typing import Any


def is_dooh_request(payload: dict[str, Any]) -> bool:
    if "dooh" not in payload:
        return False
    if payload.get("site") or payload.get("app"):
        return False
    return True
