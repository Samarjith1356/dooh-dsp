from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class ArchitectAgent(AgentRuntime):
    """Chief Software Architect — bid-path isolation and sub-1ms contracts."""

    def __init__(self) -> None:
        super().__init__(
            name="architect",
            role="Chief Software Architect",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = ArchitectAgent()
router = build_router(runtime)
