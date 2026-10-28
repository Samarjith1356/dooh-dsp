from pathlib import Path

from agents.architect.agent_runner import ArchitectAgent
from agents.memory import ErrorMemory
from agents.models import TaskIn


def test_error_memory_does_not_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.memory.MEMORY_DIR", tmp_path)
    mem = ErrorMemory("qa")
    mem.remember("ingest HTTP 403 HOST LOCAL", "clickhouse", "allow Docker network in users.d")
    mem.remember("ingest HTTP 403 HOST LOCAL", "clickhouse")
    rows = mem.load()
    assert len(rows) == 1
    assert rows[0].count == 2
    assert "DO NOT REPEAT" in mem.reminders()[0]


def test_architect_prompt_exists():
    agent = ArchitectAgent()
    assert "Golden Rule" in agent.prompt
    assert agent.prompt_path == Path(agent.prompt_path)


def test_handle_records_task():
    agent = ArchitectAgent()
    out = agent.handle(
        TaskIn(objective="Review OpenRTB no-bid for site traffic", context={"latency": True, "skip_llm": True})
    )
    assert out.agent == "architect"
    assert out.task_id
    assert any(h["to"] == "qa" for h in out.handoffs)
