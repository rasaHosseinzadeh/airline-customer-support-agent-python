"""Learning environment for enforcing the requested response signoff."""

from __future__ import annotations

import re

from relai import (
    CodeEvaluator,
    EvaluationResult,
    FixedInput,
    FixedTurn,
    RELAIEnvironment,
    SimulationResult,
)


EXPECTED_SIGNOFF = "Please let me know if you have any questions."
NORMALIZED_SIGNOFF = "please let me know if you have any questions"
TAGS = ["end-to-end", "response-ends-with-requested-signoff"]


def _normalize_for_suffix_match(text: str) -> str:
    normalized = text.casefold()
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def mock_change_seat(*args, **kwargs):
    """Mock the seat-change tool with the real tool's string return contract."""
    confirmation_code = str(kwargs.get("confirmation_code", "")).strip().upper()
    requested_seat = str(kwargs.get("requested_seat", "")).strip().upper()
    if not confirmation_code:
        return "Seat changes require a valid confirmation code."
    if not requested_seat:
        return f"Seat updated to 12A for booking {confirmation_code}."
    return f"Seat updated to {requested_seat} for booking {confirmation_code}."


def evaluate_signoff(simulation_result: SimulationResult) -> EvaluationResult:
    final_output = simulation_result.final_output
    response_text = "" if final_output is None else str(final_output).strip()
    if not response_text:
        return EvaluationResult(
            score=0.0,
            feedback=(
                "The agent did not return a final assistant reply. It needed to end "
                f"with '{EXPECTED_SIGNOFF}'."
            ),
        )

    normalized_response = _normalize_for_suffix_match(response_text)
    if normalized_response.endswith(NORMALIZED_SIGNOFF):
        return EvaluationResult(
            score=1.0,
            feedback="The final reply ends with the requested signoff.",
        )

    tail = response_text[-160:]
    return EvaluationResult(
        score=0.0,
        feedback=(
            "The final reply did not end with the requested signoff. Expected a reply "
            f"ending with '{EXPECTED_SIGNOFF}' (allowing punctuation and casing "
            f"variation), but the observed ending was: {tail!r}."
        ),
    )


environment = RELAIEnvironment(
    id="response-signoff",
    name="Response Signoff",
    description="Tests whether the agent ends its reply with the requested signoff sentence.",
    tags=TAGS,
    input=FixedInput(
        turns=[
            FixedTurn(content="What is the baggage policy for a standard ticket?"),
        ]
    ),
    mocks={
        "airline_support.agent:change_seat": mock_change_seat,
    },
    evaluators=[
        CodeEvaluator(
            id="reply-ends-with-signoff",
            description="Checks that the final assistant reply ends with the requested signoff.",
            evaluate=evaluate_signoff,
        )
    ],
)
