from app.compiler import compile_snapshot, encode_dayparts
from app.models_view import CampaignView, CreativeView


def _camp(cid: int, priority: int, venues: list[str]) -> CampaignView:
    return CampaignView(
        id=cid,
        advertiser_id=1,
        seat="seat-1",
        priority=priority,
        bid_cpm_micros=5_000_000,
        shade_factor=0.8,
        dayparts=[{"dow": 0, "hours": [8]}],
        h3_cells=[1],
        min_lat=51.3,
        max_lat=51.7,
        min_lon=-0.5,
        max_lon=0.2,
        venue_types=venues,
        creatives=[CreativeView(id=9, width=1920, height=1080, mime="image/png", cdn_url="http://x/a.png")],
    )


def test_overlap_priority():
    snap = compile_snapshot(
        [_camp(1, 10, ["roadside"]), _camp(2, 200, ["roadside"])],
        snapshot_id=7,
    )
    by_id = {c.id: c for c in snap.campaigns}
    assert by_id[2].priority > by_id[1].priority
    assert "roadside" in snap.venue_index
    assert 2 in snap.venue_index["roadside"]


def test_consult_memory_blocks_flagged_campaign():
    from app.compiler import consult_memory

    kept, notes = consult_memory(
        [_camp(1, 10, ["roadside"]), _camp(2, 10, ["roadside"])],
        [
            {
                "kind": "audit",
                "title": "compliance REJECTED alcohol roadside",
                "body": "do not compile",
                "payload": {"campaign_id": 2, "block_compile": True},
            },
            {"kind": "decision", "title": "cap-raise rejected", "body": "Sam rejected cap", "payload": {}},
            {"kind": "architecture", "title": "Bid-path isolation", "body": "no postgres on bidder", "payload": {}},
        ],
    )
    assert [c.id for c in kept] == [1]
    assert any("blocked campaign 2" in n for n in notes)
    assert any("cap-raise rejected" in n for n in notes)
    assert any(n.startswith("rule:") for n in notes)


def test_daypart_bits_roundtrip():
    b64 = encode_dayparts([{"dow": 1, "hours": [7, 8]}])
    import base64

    raw = base64.b64decode(b64)
    assert len(raw) == 21
    idx = 1 * 24 + 7
    assert raw[idx // 8] & (1 << (idx % 8))
