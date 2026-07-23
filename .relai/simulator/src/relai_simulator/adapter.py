from __future__ import annotations

from agents import Runner

from airline_support.agent import create_airline_agent
from relai_simulator.adapter_contract import AgentAdapter, AgentTurnResult


class ProjectAgentAdapter:
    def __init__(self) -> None:
        self.agent_or_tools = create_airline_agent()

    async def run_turn(self, user_input: object) -> AgentTurnResult:
        result = await Runner.run(self.agent_or_tools, input=user_input)
        return AgentTurnResult(assistant_message=str(result.final_output))


def build_agent_adapter() -> AgentAdapter:
    return ProjectAgentAdapter()
