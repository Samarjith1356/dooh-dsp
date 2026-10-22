from io import BytesIO

from PIL import Image

from app.creative import ScreenSpec, validate_asset


def spec() -> ScreenSpec:
    return ScreenSpec(
        id=1,
        publisher="JCDecaux",
        format_code="ROADSIDE_LANDSCAPE",
        width=1920,
        height=1080,
        aspect="16:9",
        max_bytes=12_000_000,
        codecs=["jpeg", "png"],
        max_duration_ms=10000,
        venue_types=["roadside"],
    )


def png(w: int, h: int) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(20, 20, 20)).save(buf, format="PNG")
    return buf.getvalue()


def test_reject_wrong_aspect():
    errors = validate_asset("ad.png", png(100, 100), spec())
    fields = {e.field for e in errors}
    assert "dimensions" in fields
    assert "aspect" in fields


def test_accept_correct_size():
    errors = validate_asset("ad.png", png(1920, 1080), spec())
    assert errors == []
