from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class FrontendAgent(AgentRuntime):
    """Enterprise UX for the Next.js control center."""

    def __init__(self) -> None:
        super().__init__(
            name="frontend",
            role="Enterprise UX & UI Control Center",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = FrontendAgent()
router = build_router(runtime)
