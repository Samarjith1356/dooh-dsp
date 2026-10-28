from agents.devops.auditor import audit


def test_offline_audit_flags_clickhouse_wildcard_and_keeps_bidder_isolated():
    result = audit(live=False)
    ids = {f.id: f for f in result.findings}
    assert "ch-wildcard" in ids
    assert ids["ch-wildcard"].severity == "critical"
    assert result.bidder_isolation_ok is True
    assert "bidder-isolation" in ids
    assert result.verdict == "HARDENING_REQUIRED"


def test_chaos_playbook_does_not_fail_open_budget():
    from agents.devops.auditor import CHAOS_PLAYBOOK

    assert "fail-open" in CHAOS_PLAYBOOK["redis_disconnect"]["never_repeat"]
