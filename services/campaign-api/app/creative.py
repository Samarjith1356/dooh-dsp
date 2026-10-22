from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image

IMAGE_MIMES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
VIDEO_MIMES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class ScreenSpec:
    id: int
    publisher: str
    format_code: str
    width: int
    height: int
    aspect: str
    max_bytes: int
    codecs: list[str]
    max_duration_ms: int
    venue_types: list[str]


def aspect_of(w: int, h: int) -> str:
    if w == 0 or h == 0:
        return "0:0"
    from math import gcd

    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def guess_mime(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return IMAGE_MIMES.get(ext) or VIDEO_MIMES.get(ext) or "application/octet-stream"


def validate_asset(
    filename: str,
    data: bytes,
    spec: ScreenSpec,
    duration_ms: int = 0,
) -> list[ValidationError]:
    errors: list[ValidationError] = []
    mime = guess_mime(filename)
    ext = Path(filename).suffix.lower()

    if len(data) > spec.max_bytes:
        errors.append(
            ValidationError("file", f"file is {len(data)} bytes; max for {spec.format_code} is {spec.max_bytes}")
        )

    if ext in IMAGE_MIMES:
        try:
            img = Image.open(BytesIO(data))
            w, h = img.size
        except Exception as exc:  # noqa: BLE001
            errors.append(ValidationError("file", f"cannot decode image: {exc}"))
            return errors
        if w != spec.width or h != spec.height:
            errors.append(
                ValidationError(
                    "dimensions",
                    f"got {w}x{h}; {spec.publisher} {spec.format_code} requires {spec.width}x{spec.height}",
                )
            )
        got_aspect = aspect_of(w, h)
        if got_aspect != spec.aspect:
            errors.append(ValidationError("aspect", f"got {got_aspect}; required {spec.aspect}"))
        codec = img.format.lower() if img.format else "unknown"
        allowed = {c.lower() for c in spec.codecs}
        if codec not in allowed and mime.split("/")[-1] not in allowed:
            errors.append(ValidationError("codec", f"got {codec}; allowed {sorted(allowed)}"))
    elif ext in VIDEO_MIMES:
        if "h264" not in {c.lower() for c in spec.codecs} and "mp4" not in {c.lower() for c in spec.codecs}:
            errors.append(ValidationError("codec", f"video not in allowed codecs {spec.codecs}"))
        if spec.max_duration_ms and duration_ms and duration_ms > spec.max_duration_ms:
            errors.append(
                ValidationError(
                    "duration",
                    f"duration {duration_ms}ms exceeds max {spec.max_duration_ms}ms for {spec.format_code}",
                )
            )
    else:
        errors.append(ValidationError("file", f"unsupported extension {ext}"))

    return errors
