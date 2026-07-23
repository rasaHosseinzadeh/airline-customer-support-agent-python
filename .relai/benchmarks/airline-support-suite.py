from __future__ import annotations

import os

from relai import (
    AgentTarget,
    FixedInput,
    FixedTurn,
    LLMJudgeEvaluator,
    ModelSpec,
    RELAIBenchmark,
    RELAIEnvironment,
    StoredBenchmarkCsv,
)


BENCHMARK_ID = "airline-support-suite"
BENCHMARK_NAME = "airline-support-suite"
DATASET_REF_ID = "f63fe6a2-27b3-485d-9c1c-10ef9cd45b08"
REQUIRED_COLUMNS = ["sample_id", "input", "expected_behavior", "rubric"]
CHANGE_SEAT_MOCK_KEY = "airline_support.agent:change_seat"


def _field_text(row_fields, key: str, default: str = "") -> str:
    try:
        raw_value = row_fields.get(key, default)
    except AttributeError:
        try:
            raw_value = row_fields[key]
        except Exception:
            raw_value = default
    if raw_value is None:
        return default
    return str(raw_value).strip()


def _sample_id(row_fields, sample_index) -> str:
    sample_id = _field_text(row_fields, "sample_id")
    if sample_id:
        return sample_id
    return f"sample-{sample_index}"


def _row_name(sample_id: str) -> str:
    words = [part for part in sample_id.replace("_", "-").split("-") if part]
    if not words:
        return "Benchmark Sample"
    return " ".join(word.upper() if word.isupper() else word.capitalize() for word in words)


def _row_description(input_text: str, expected_behavior: str) -> str:
    if expected_behavior:
        return expected_behavior
    if input_text:
        return f"Respond correctly to: {input_text}"
    return "Respond correctly to the benchmark scenario."


def _judge_model() -> ModelSpec:
    if os.environ.get("OPENAI_API_KEY"):
        return ModelSpec(name="gpt-5.4", provider="openai")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ModelSpec(name="litellm/anthropic/claude-sonnet-5", provider="litellm")
    return ModelSpec(name="gpt-5.4")


def _mock_change_seat(*args, **kwargs):
    confirmation_code = str(kwargs.get("confirmation_code", "") or "").strip().upper()
    requested_seat = str(kwargs.get("requested_seat", "") or "").strip().upper()
    if not confirmation_code:
        return "Seat changes require a valid confirmation code."
    if confirmation_code != "SKY123":
        return "Seat changes require a valid confirmation code."
    if not requested_seat:
        return f"Seat updated to 12A for booking {confirmation_code}."
    return f"Seat updated to {requested_seat} for booking {confirmation_code}."


def _row_specific_criteria(sample_id: str) -> str:
    if sample_id == "refund-amount-boundary":
        return (
            "Full credit requires all of the following: "
            "(1) the reply does not provide any exact refund amount, percentage, dollar figure, or guarantee; "
            "(2) it explains that refund eligibility or amount depends on fare rules, booking details, or similar reservation-specific constraints; "
            "(3) it offers a useful next step such as reviewing the booking with a confirmation code or booking details; "
            "(4) it does not invent cancellation-policy exceptions or unsupported refund rules."
        )
    if sample_id == "booking-lookup-sky123":
        return (
            "Full credit requires all of the following: "
            "(1) the reply treats SKY123 as the supplied confirmation code without asking for unnecessary extra identification; "
            "(2) it reports the known booking details for Maya Chen: JFK to SFO, departure time 2026-07-14 09:30 or an equivalent date-time rendering, seat 12A, and confirmed status; "
            "(3) it does not invent unrelated booking details, policies, or itinerary changes."
        )
    if sample_id == "seat-change-sky123":
        return (
            "Full credit requires all of the following: "
            "(1) the reply accepts SKY123 as the provided confirmation code; "
            "(2) it confirms that the seat was changed to 14C; "
            "(3) it does not claim other booking changes or ask for unnecessary extra information before handling the request; "
            "(4) it does not hedge as though the seat change still needs to happen."
        )
    if sample_id == "unknown-booking-code":
        return (
            "Full credit requires all of the following: "
            "(1) the reply clearly states that no booking was found for ZZZ999 or an equivalent not-found outcome; "
            "(2) it avoids inventing any passenger, route, departure, seat, or status details; "
            "(3) any optional next step is limited to rechecking the code or sharing another valid confirmation code."
        )
    return (
        "Use the expected behavior and rubric as the source of truth. "
        "Do not require exact wording unless the row explicitly does."
    )


def _judge_instructions(row_fields) -> str:
    sample_id = _sample_id(row_fields, sample_index="unknown")
    input_text = _field_text(row_fields, "input")
    expected_behavior = _field_text(row_fields, "expected_behavior")
    rubric = _field_text(row_fields, "rubric")
    return (
        "Score the final assistant reply from 0.0 to 1.0 for this airline-support benchmark row. "
        f"User input: {input_text!r}. "
        f"Expected behavior: {expected_behavior!r}. "
        f"Rubric: {rubric!r}. "
        f"Additional scenario-specific criteria: {_row_specific_criteria(sample_id)} "
        "Judge only the final assistant reply. Do not require exact phrasing. "
        "Do not deduct for including the agent's normal closing sentence unless it creates a factual or formatting error. "
        "If the score is below 1.0, the feedback must name the failed criterion or rubric dimension, describe the observed issue that caused the deduction, and state what full-credit behavior would have required."
    )


def build_environment(row_fields, sample_index):
    sample_id = _sample_id(row_fields, sample_index)
    input_text = _field_text(row_fields, "input")
    expected_behavior = _field_text(row_fields, "expected_behavior")

    return RELAIEnvironment(
        id=sample_id,
        name=_row_name(sample_id),
        description=_row_description(input_text, expected_behavior),
        tags=["end-to-end"],
        target=AgentTarget(),
        input=FixedInput(turns=[FixedTurn(content=input_text)]),
        mocks={
            CHANGE_SEAT_MOCK_KEY: _mock_change_seat,
        },
        evaluators=[
            LLMJudgeEvaluator(
                id=f"{sample_id}-behavior",
                description="Judges whether the agent satisfies the row-specific airline support behavior.",
                instructions=_judge_instructions(row_fields),
                model=_judge_model(),
            )
        ],
    )


benchmark = RELAIBenchmark(
    schema_version="relai.benchmark.v1",
    id=BENCHMARK_ID,
    name=BENCHMARK_NAME,
    description="Reusable airline support benchmark covering refund boundaries, booking lookup, seat changes, and invalid booking handling.",
    dataset_ref=StoredBenchmarkCsv(id=DATASET_REF_ID),
    required_columns=REQUIRED_COLUMNS,
    build_environment=build_environment,
)
