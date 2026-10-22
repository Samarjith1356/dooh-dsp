from __future__ import annotations

from pathlib import Path

from app.config import CREATIVE_DIR, CREATIVE_PUBLIC_URL


def put_creative(key: str, data: bytes, content_type: str) -> str:
    dest = Path(CREATIVE_DIR) / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return f"{CREATIVE_PUBLIC_URL}/{key}"
