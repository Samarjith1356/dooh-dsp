from agents.qa.suite import run_in_process


def test_in_process_suite_covers_golden_rule_and_illegal_draft_active():
    report = run_in_process()
    ids = {c.id: c for c in report.cases}
    assert ids["illegal-draft-active"].ok
    assert ids["compiles-only-active"].ok
    assert ids["L3-golden-rule"].ok
    assert ids["compliance-hyperbole-guarantee"].ok
    assert ids["compliance-clean-dublin-commute"].ok
