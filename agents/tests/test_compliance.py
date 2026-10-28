from agents.compliance.scanner import QA_VECTORS, AuditRequest, audit


def test_qa_vectors():
    for vector in QA_VECTORS:
        got = audit(AuditRequest(**vector["request"]))
        assert got.verdict == vector["expect"], f"{vector['id']}: {got.verdict} != {vector['expect']} {got.findings}"


def test_dublin_brand_awareness_approved():
    result = audit(
        AuditRequest(
            goal="Run a 2-week brand awareness campaign targeting commuters in Dublin",
            countries=["IE"],
            venue_types=["transit.rail"],
        )
    )
    assert result.verdict == "APPROVED"
    assert "IE" in result.markets_reviewed
