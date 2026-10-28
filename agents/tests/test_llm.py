from agents.llm import LLMNotConfigured, complete, provider, status


def test_status_none_when_keys_empty(monkeypatch):
    monkeypatch.setattr("agents.llm.XAI_API_KEY", "")
    st = status()
    assert st["configured"] is False
    assert st["provider"] == "none"


def test_complete_posts_xai_chat_completions(monkeypatch):
    monkeypatch.setattr("agents.llm.XAI_API_KEY", "xai-test")
    monkeypatch.setattr("agents.llm.XAI_BASE_URL", "https://api.x.ai/v1")
    monkeypatch.setattr("agents.llm.AGENT_LLM_MODEL", "grok-4.7")

    class FakeResp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "isolation holds"}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json, headers):
            assert url == "https://api.x.ai/v1/chat/completions"
            assert headers["Authorization"] == "Bearer xai-test"
            assert json["model"] == "grok-4.7"
            assert json["messages"][0]["role"] == "system"
            return FakeResp()

    monkeypatch.setattr("agents.llm.httpx.Client", FakeClient)
    text = complete(system="You are architect.", user="Is Postgres on the bid path?")
    assert text == "isolation holds"


def test_complete_requires_xai_key(monkeypatch):
    monkeypatch.setattr("agents.llm.XAI_API_KEY", "")
    try:
        complete(system="s", user="u")
        raise AssertionError("expected LLMNotConfigured")
    except LLMNotConfigured:
        pass


def test_openai_is_ignored(monkeypatch):
    monkeypatch.setattr("agents.llm.XAI_API_KEY", "")
    p = provider()
    assert p["name"] == "none"


def test_default_model_is_grok(monkeypatch):
    monkeypatch.setattr("agents.llm.XAI_API_KEY", "xai-test")
    monkeypatch.setattr("agents.llm.AGENT_LLM_MODEL", "")
    p = provider()
    assert p["name"] == "xai"
    assert p["model"] == "grok-4.7"
