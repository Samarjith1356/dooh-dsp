from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.config import MEMORY_DIR
from agents.models import ErrorRecord


class ErrorMemory:
    """Durable error log so agents do not repeat known failure modes."""

    def __init__(self, agent: str) -> None:
        self.agent = agent
        self.dir = MEMORY_DIR / agent
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "errors.jsonl"

    def fingerprint(self, message: str, source: str) -> str:
        raw = f"{self.agent}|{source}|{message.strip().lower()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def remember(self, message: str, source: str, resolution: str = "") -> ErrorRecord:
        fp = self.fingerprint(message, source)
        existing = {r.fingerprint: r for r in self.load()}
        if fp in existing:
            rec = existing[fp]
            rec.count += 1
            rec.seen_at = datetime.now(timezone.utc)
            if resolution:
                rec.resolution = resolution
        else:
            rec = ErrorRecord(
                fingerprint=fp,
                message=message.strip(),
                source=source,
                seen_at=datetime.now(timezone.utc),
                resolution=resolution,
            )
            existing[fp] = rec
        self._rewrite(list(existing.values()))
        return rec

    def load(self) -> list[ErrorRecord]:
        if not self.path.exists():
            return []
        rows: list[ErrorRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(ErrorRecord.model_validate_json(line))
        return rows

    def reminders(self, limit: int = 8) -> list[str]:
        rows = sorted(self.load(), key=lambda r: r.seen_at, reverse=True)[:limit]
        out = []
        for r in rows:
            hint = f"DO NOT REPEAT [{r.fingerprint}]: {r.message}"
            if r.resolution:
                hint += f" | fix: {r.resolution}"
            out.append(hint)
        return out

    def _rewrite(self, rows: list[ErrorRecord]) -> None:
        tmp = self.path.with_suffix(".tmp")
        payload = "\n".join(r.model_dump_json() for r in rows)
        tmp.write_text(payload + ("\n" if payload else ""), encoding="utf-8")
        tmp.replace(self.path)
