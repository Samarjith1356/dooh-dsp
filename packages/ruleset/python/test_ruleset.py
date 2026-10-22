from ruleset import RulesSnapshot, ShadingParams, CompiledCampaign, CreativeRef


def test_roundtrip():
    snap = RulesSnapshot(
        snapshot_id=1,
        compiled_at_unix=1,
        epoch=1,
        campaigns=[
            CompiledCampaign(
                id=1,
                advertiser_id=1,
                seat="s",
                priority=1,
                bid_cpm_micros=1,
                shading=ShadingParams(),
                daypart_bits="AA==",
                h3_cells=[1],
                min_lat=0,
                max_lat=1,
                min_lon=0,
                max_lon=1,
                venue_types=["roadside"],
                creatives=[CreativeRef(1, 1920, 1080, "image/png", "http://x")],
                budget_token="budget:1:remaining_micros",
            )
        ],
        venue_index={"roadside": [1]},
        h3_index={"1": [1]},
        deal_index={},
    )
    again = RulesSnapshot.from_dict(snap.to_dict())
    assert again.campaigns[0].id == 1
    assert again.venue_index["roadside"] == [1]
