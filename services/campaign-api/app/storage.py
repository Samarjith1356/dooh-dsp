from __future__ import annotations

import logging
from io import BytesIO

from app.config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_PUBLIC_URL,
    MINIO_SECRET_KEY,
)

log = logging.getLogger(__name__)


def put_creative(key: str, data: bytes, content_type: str) -> str:
    try:
        from minio import Minio

        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,
        )
        if not client.bucket_exists(MINIO_BUCKET):
            client.make_bucket(MINIO_BUCKET)
        client.put_object(
            MINIO_BUCKET,
            key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return f"{MINIO_PUBLIC_URL}/{key}"
    except Exception as exc:  # noqa: BLE001
        log.warning("minio unavailable, using local uri stub: %s", exc)
        return f"{MINIO_PUBLIC_URL}/{key}"
