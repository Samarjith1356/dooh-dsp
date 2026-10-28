from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class QAAgent(AgentRuntime):
    """Zero-error integration testing for OpenRTB, state machine, and latency."""

    def __init__(self) -> None:
        super().__init__(
            name="qa",
            role="Zero-Error Integration Testing",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = QAAgent()
router = build_router(runtime)
