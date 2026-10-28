from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class ProductAgent(AgentRuntime):
    """Client AI orchestrator — goals to approved plans, never live bid rules."""

    def __init__(self) -> None:
        super().__init__(
            name="product",
            role="Client AI Orchestrator Manager",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = ProductAgent()
router = build_router(runtime)
