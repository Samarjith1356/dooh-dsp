from memory.store import metrics, recall, remember, reset_for_tests, seed_architecture


def test_remember_and_recall_roundtrip():
    reset_for_tests()
    remember(
        kind="campaign",
        source="test",
        title="Approved Dublin commute plan",
        body="campaign 9 pending_approval → active",
        payload={"campaign_id": 9},
    )
    hits = recall(query="dublin commute", kinds=["campaign"], limit=5)
    assert hits
    assert hits[0]["payload"]["campaign_id"] == 9
    st = metrics()
    assert st["chunks"] >= 1
    assert st["learning"]["tracking"] is True


def test_seed_architecture_idempotent():
    reset_for_tests()
    seed_architecture()
    first = len(recall(kinds=["architecture"], limit=50))
    seed_architecture()
    second = len(recall(kinds=["architecture"], limit=50))
    assert second == first
    assert first >= 1
