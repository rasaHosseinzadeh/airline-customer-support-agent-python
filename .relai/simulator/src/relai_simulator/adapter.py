from __future__ import annotations

from agents import Agent, Runner

from airline_support.agent import create_airline_agent
from relai_simulator.adapter_contract import AgentAdapter, AgentTurnResult


class AirlineSupportAdapter:
    """Thin adapter around the SkyServe airline support agent.

    ``agent_or_tools`` exposes the framework ``Agent`` so the generic runner can
    apply tool mocks to its ``@function_tool`` boundaries before each turn.
    """

    def __init__(self) -> None:
        self._agent: Agent = create_airline_agent()
        self.agent_or_tools: Agent = self._agent

    async def run_turn(self, user_input: object) -> AgentTurnResult:
        result = await Runner.run(self._agent, input=str(user_input))
        return AgentTurnResult(assistant_message=result.final_output)


def build_agent_adapter() -> AgentAdapter:
    return AirlineSupportAdapter()
