"""RELAI learning environment: airline agent must sign off on every response."""

import re

from relai import (
    CodeEvaluator,
    EvaluationResult,
    FixedInput,
    FixedTurn,
    RELAIEnvironment,
    SimulationResult,
)


# Scope tag plus a normalized scenario+expectation summary tag.
TAGS = ["end-to-end", "every-response-ends-with-signoff"]

# The required closing line, normalized (lowercased, no trailing punctuation).
# The prompt explicitly permits variations in punctuation and casing.
REQUIRED_SIGNOFF = "please let me know if you have any questions"


def mock_lookup_booking(*args, **kwargs):
    """Mock for airline_support.agent:lookup_booking: returns a deterministic
    booking summary string, matching the real tool's string return contract."""
    return (
        "Maya Chen is booked on JFK to SFO departing 2026-07-14 09:30. "
        "Seat 12A. Status: confirmed."
    )


def mock_baggage_policy(*args, **kwargs):
    """Mock for airline_support.agent:baggage_policy: returns a deterministic
    baggage policy string, matching the real tool's string return contract."""
    return "Standard tickets include one carry-on and one checked bag up to 50 pounds."


def mock_change_seat(*args, **kwargs):
    """Mock for airline_support.agent:change_seat: returns a deterministic
    confirmation string so the in-memory booking state is never mutated."""
    return "Seat updated to 14C for booking SKY123."


def _entry_role(entry) -> str:
    if isinstance(entry, dict):
        raw = entry.get("role") or entry.get("type") or ""
    else:
        raw = getattr(entry, "role", None) or getattr(entry, "type", None) or ""
    return str(raw).lower()


def _entry_text(entry):
    keys = ("content", "text", "assistant_message", "message", "final_output")
    if isinstance(entry, dict):
        for key in keys:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None
    for key in keys:
        value = getattr(entry, key, None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _collect_agent_replies(simulation_result: SimulationResult) -> list[str]:
    """Gather every assistant/agent reply across all turns.

    Falls back to the final output when no per-turn transcript is exposed."""
    replies: list[str] = []
    for attr in ("transcript", "events", "messages", "turns"):
        container = getattr(simulation_result, attr, None)
        entries = getattr(container, "events", container)
        if isinstance(entries, (list, tuple)):
            for entry in entries:
                role = _entry_role(entry)
                if role and ("assistant" in role or "agent" in role) and "user" not in role:
                    text = _entry_text(entry)
                    if text:
                        replies.append(text)
        if replies:
            break
    if not replies:
        final_output = getattr(simulation_result, "final_output", None)
        if isinstance(final_output, str) and final_output.strip():
            replies.append(final_output)
    return replies


def _ends_with_signoff(reply: str) -> bool:
    normalized = re.sub(r"\s+", " ", reply.strip().lower())
    # Drop trailing punctuation/whitespace so "...questions.", "...questions!",
    # or a trailing newline all count as the same normalized sign-off.
    normalized = normalized.rstrip(" \t\r\n.!?…")
    return normalized.endswith(REQUIRED_SIGNOFF)


def check_signoff(simulation_result: SimulationResult) -> EvaluationResult:
    replies = _collect_agent_replies(simulation_result)
    if not replies:
        return EvaluationResult(
            score=0.0,
            feedback=(
                "No agent replies were found to evaluate. Expected every reply to "
                f"end with the sign-off '{REQUIRED_SIGNOFF.capitalize()}.' "
                "(punctuation/casing variations allowed)."
            ),
        )

    failing = []
    for index, reply in enumerate(replies, start=1):
        if not _ends_with_signoff(reply):
            tail = re.sub(r"\s+", " ", reply.strip())[-70:]
            failing.append((index, tail))

    total = len(replies)
    if not failing:
        return EvaluationResult(
            score=1.0,
            feedback=(
                f"All {total} agent reply/replies end with the required closing "
                f"'{REQUIRED_SIGNOFF.capitalize()}.' (punctuation/casing variations "
                "accepted)."
            ),
        )

    detail = "; ".join(
        f"reply #{idx} of {total} ended with \"…{tail}\"" for idx, tail in failing
    )
    return EvaluationResult(
        score=0.0,
        feedback=(
            f"Missing required sign-off in {len(failing)} of {total} agent reply/replies: "
            f"{detail}. Every response must end with the closing line "
            f"'{REQUIRED_SIGNOFF.capitalize()}.' (trailing punctuation and letter "
            "casing may vary, but the closing sentence itself must be present as the "
            "last line). The problem is missing required text, not wrong content."
        ),
    )


environment = RELAIEnvironment(
    id="response-signoff",
    name="Airline Agent Sign-off on Every Reply",
    description=(
        "Checks that the airline support agent ends every response with the "
        "required closing sign-off across a multi-turn conversation."
    ),
    tags=TAGS,
    input=FixedInput(
        turns=[
            FixedTurn(content="Hi, what's the baggage allowance on a standard ticket?"),
            FixedTurn(content="Great. I'd also like to change my seat to 14C."),
        ]
    ),
    mocks={
        "airline_support.agent:lookup_booking": mock_lookup_booking,
        "airline_support.agent:baggage_policy": mock_baggage_policy,
        "airline_support.agent:change_seat": mock_change_seat,
    },
    evaluators=[
        CodeEvaluator(
            id="signoff-on-every-reply",
            description=(
                "Verifies every agent reply ends with the required sign-off, "
                "tolerating punctuation and casing variations."
            ),
            evaluate=check_signoff,
        )
    ],
)
