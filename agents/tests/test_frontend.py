from agents.frontend.auditor import audit


def test_four_pillars_and_ts5():
    result = audit()
    assert result.pillars["command_center"]
    assert result.pillars["inventory"]
    assert result.pillars["studio"]
    assert result.pillars["ledger"]
    ids = {f.id: f for f in result.findings}
    assert ids["typescript-5"].severity == "pass"
    assert result.rbac_server_enforced is False


def test_does_not_claim_server_rbac():
    result = audit()
    warn = next(f for f in result.findings if f.id == "rbac-client-only")
    assert warn.severity == "warn"
