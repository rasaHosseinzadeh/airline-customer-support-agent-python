from __future__ import annotations

from collections.abc import Sequence

from agents import Runner

from airline_support.agent import create_airline_agent
from relai_simulator.adapter_contract import AgentAdapter
from relai_simulator.adapter_contract import AgentTurnResult


class ProjectAgentAdapter:
    def __init__(self) -> None:
        self.agent = create_airline_agent()
        self.agent_or_tools = self.agent
        self._messages: list[dict[str, str]] = []

    async def run_turn(self, user_input: object) -> AgentTurnResult:
        if not isinstance(user_input, str):
            raise TypeError(
                "Airline support simulator turns must be strings matching the terminal user message."
            )

        self._messages.append({"role": "user", "content": user_input})
        result = await Runner.run(self.agent, input=list(self._messages))
        assistant_message = _coerce_assistant_message(getattr(result, "final_output", None))

        if assistant_message is not None:
            self._messages.append({"role": "assistant", "content": assistant_message})

        return AgentTurnResult(
            assistant_message=assistant_message,
            metadata={"turn_input_type": "string"},
        )


def build_agent_adapter() -> AgentAdapter:
    return ProjectAgentAdapter()


def _coerce_assistant_message(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return "\n".join(str(item) for item in value)
    return str(value)
