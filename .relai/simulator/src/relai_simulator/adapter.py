from __future__ import annotations

from agents import Runner

from airline_support.agent import create_airline_agent

from relai_simulator.adapter_contract import AgentAdapter


class ProjectAgentAdapter:
    """Thin adapter around the airline support OpenAI Agents SDK agent.

    The public turn value is the plain user message string that learning
    environments provide in ``FixedTurn.content``.
    """

    def __init__(self) -> None:
        # Build the agent once so the generic runner can apply tool mocks to the
        # agent's FunctionTool objects via ``agent_or_tools``.
        self._agent = create_airline_agent()
        self.agent_or_tools = self._agent

    async def run_turn(self, user_input: object):
        result = await Runner.run(self._agent, input=user_input)
        return result.final_output


def build_agent_adapter() -> AgentAdapter:
    return ProjectAgentAdapter()
