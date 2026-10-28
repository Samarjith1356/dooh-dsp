from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class DevOpsAgent(AgentRuntime):
    """SRE and infrastructure — Compose, Redis, ClickHouse, network ACLs."""

    def __init__(self) -> None:
        super().__init__(
            name="devops",
            role="SRE & Infrastructure",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = DevOpsAgent()
router = build_router(runtime)
