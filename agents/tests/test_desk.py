from agents.desk import remap_commute_dow


def test_remap_commute_dow_to_go_sunday0():
    blocks = [{"dow": d, "hours": [7, 8]} for d in range(0, 5)]
    mapped = remap_commute_dow(blocks)
    assert [b["dow"] for b in mapped] == [1, 2, 3, 4, 5]
