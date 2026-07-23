"""RELAI learning environment generated from a sandboxed log/feedback pass."""

import re

from relai import (
    CodeEvaluator,
    EvaluationResult,
    FixedInput,
    FixedTurn,
    RELAIEnvironment,
    SimulationResult,
)


def mock_baggage_policy(*args, **kwargs):
    """Mock for airline_support.agent:baggage_policy: Pure function over the ticket_type argument with no external calls or shared state; deterministic and safe to run live."""
    return "Standard tickets include one carry-on and one checked bag up to 50 pounds."


def mock_change_seat(*args, **kwargs):
    """Mock for airline_support.agent:change_seat: Mutates the shared in-memory BOOKINGS dataset, so live runs can leak seat-change state across scenarios and simulation reruns; mock to keep runs deterministic and non-destructive."""
    return "Seat updated to 14C for booking SKY123."


# The prompt allows punctuation/casing variation, so the closed-set sign-off
# phrase is matched with a normalized, case-insensitive pattern anchored to
# the end of the response.
SIGNOFF_PATTERN = re.compile(
    r"please let me know if you have any questions[.!?]*\s*$",
    re.IGNORECASE,
)


def check_signoff(simulation_result: SimulationResult) -> EvaluationResult:
    final_output = (simulation_result.final_output or "").strip()
    if SIGNOFF_PATTERN.search(final_output):
        return EvaluationResult(
            score=1.0,
            feedback=(
                "Response ends with the required sign-off "
                "('Please let me know if you have any questions.'), "
                "allowing for punctuation/casing variation."
            ),
        )
    tail = final_output[-80:] if final_output else "(empty response)"
    return EvaluationResult(
        score=0.0,
        feedback=(
            "Response is missing the required closing sign-off. Every response must end with "
            "'Please let me know if you have any questions.' (casing and punctuation variations "
            f"are allowed, but it must appear at the very end). The response actually ended with: {tail!r}"
        ),
    )


environment = RELAIEnvironment(
    id="response-signoff",
    name="Response sign-off formatting",
    description="Checks that the airline support agent closes its reply with the required 'Please let me know if you have any questions.' sign-off.",
    tags=["end-to-end", "response-ends-with-required-signoff"],
    input=FixedInput(
        turns=[
            FixedTurn(
                content="What's the baggage allowance for a standard economy ticket?",
            ),
        ],
    ),
    mocks={
        "airline_support.agent:baggage_policy": mock_baggage_policy,
        "airline_support.agent:change_seat": mock_change_seat,
    },
    evaluators=[
        CodeEvaluator(
            id="signoff-present",
            description="Checks that the response ends with the required sign-off sentence, allowing punctuation/casing variation.",
            evaluate=check_signoff,
        ),
    ],
)
