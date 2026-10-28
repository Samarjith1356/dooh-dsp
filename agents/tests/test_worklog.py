from agents.worklog import begin_turn, current_job, finish_turn, thread, thread_bundle


def test_thread_persists_across_reopen(monkeypatch):
    monkeypatch.setattr("agents.worklog._redis", lambda: None)
    from agents import worklog as w

    w._local_threads.clear()
    w._local_current.clear()
    w._local_history.clear()
    begin_turn("architect", "Build a customer journey on the dashboard")
    finish_turn("architect", "I will add an advertiser wizard under Command Center.")
    bundle = thread_bundle("architect")
    assert bundle["status"] == "WORKING"
    assert current_job("architect")["title"].startswith("Build a customer")
    msgs = thread("architect")
    assert msgs[0]["role"] == "sam"
    assert msgs[1]["role"] == "agent"
    reopen = thread_bundle("architect")
    assert len(reopen["messages"]) == 2


def test_idle_archives_job_keeps_chat(monkeypatch):
    monkeypatch.setattr("agents.worklog._redis", lambda: None)
    from agents import worklog as w

    w._local_threads.clear()
    w._local_current.clear()
    w._local_history.clear()
    begin_turn("frontend", "New advertiser journey")
    finish_turn("frontend", "Drafted the flow.")
    begin_turn("frontend", "done")
    assert current_job("frontend") is None
    bundle = thread_bundle("frontend")
    assert bundle["status"] == "IDLE"
    assert bundle["history"]
    assert len(bundle["messages"]) >= 2
