from agents.product.planner import classify, orchestrate, parse_goal


def test_dublin_commute_plan_is_ie_transit_unapproved():
    plan, _ = parse_goal("Run a 2-week brand awareness campaign targeting commuters in Dublin")
    assert plan.countries == ["IE"]
    assert "transit.rail" in plan.venue_allowlist
    assert plan.currency == "GBP"
    assert plan.bid_cpm_micros == 6_500_000
    assert plan.approved is False
    assert plan.needs_approval is True
    assert all(d["dow"] in range(0, 5) for d in plan.dayparts)


def test_london_billboard():
    plan, _ = parse_goal("UK roadside billboard brand burst in London")
    assert plan.countries == ["GB"]
    assert "roadside" in plan.venue_allowlist


def test_guarantee_is_not_approval_ready():
    result = orchestrate("We guarantee you will be the best in the world in Dublin")
    assert result.compliance is not None
    assert result.compliance.verdict == "REJECTED"
    assert result.can_present_approval is False
    assert result.next_state == "draft"
    assert "cannot send this goal for approval" in result.reply.lower()


def test_intents():
    assert classify("performance this week") == "performance"
    assert classify("how is my campaign") == "performance"
    assert classify("catalog please") == "catalog"
    assert classify("commuters in Dublin") == "plan"
