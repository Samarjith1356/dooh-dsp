from pathlib import Path

from agents.runtime import AgentRuntime, build_router


class AnalyticsAgent(AgentRuntime):
    """Data and pacing intelligence over ClickHouse and Redis remaining micros."""

    def __init__(self) -> None:
        super().__init__(
            name="analytics",
            role="Data & Pacing Intelligence",
            prompt_path=Path(__file__).with_name("prompt.md"),
        )


runtime = AnalyticsAgent()
router = build_router(runtime)
