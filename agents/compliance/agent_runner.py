from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class ComplianceAgent(AgentRuntime):
    """ASA/CAP regulatory guard for GB/IE campaign copy and plans."""

    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            role="ASA/CAP Regulatory Guard",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = ComplianceAgent()
router = build_router(runtime)
