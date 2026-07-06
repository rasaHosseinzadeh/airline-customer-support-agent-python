import re
from datetime import datetime

from airline_support.agent import BOOKINGS
from relai import (
    AgentTarget,
    CodeEvaluator,
    EvaluationResult,
    FixedInput,
    FixedTurn,
    RELAIBenchmark,
    RELAIEnvironment,
    StoredBenchmarkCsv,
)


BENCHMARK_ID = "airline-support-suite"
BENCHMARK_NAME = "airline-support-suite"
DATASET_REF_ID = "b4580ba3-8918-4cf0-8d7d-4c38fadcaff4"
REQUIRED_COLUMNS = ["sample_id", "input", "expected_behavior"]


def mock_change_seat(confirmation_code: str, requested_seat: str) -> str:
    code = confirmation_code.strip().upper()
    booking = BOOKINGS.get(code)
    if booking is None:
        return "Seat changes require a valid confirmation code."
    seat = requested_seat.strip().upper()
    return f"Seat updated to {seat} for booking {code}."


def _row_value(row_fields, key: str) -> str:
    return str(row_fields.get(key, "")).strip()


def _final_reply(simulation_result) -> str | None:
    final_output = getattr(simulation_result, "final_output", None)
    if final_output is None:
        return None
    return str(final_output).strip()


def _lower(text: str) -> str:
    return text.lower()


def _extract_confirmation_code(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{3}\d{3}\b", text.upper())
    if match is None:
        return None
    return match.group(0)


def _extract_requested_seat(text: str) -> str | None:
    match = re.search(r"\b\d{1,2}[A-F]\b", text.upper())
    if match is None:
        return None
    return match.group(0)


def _contains_any(text: str, options: list[str]) -> bool:
    return any(option in text for option in options)


def _departure_variants(raw_departure: str) -> tuple[list[str], list[str]]:
    try:
        departure = datetime.strptime(raw_departure, "%Y-%m-%d %H:%M")
    except ValueError:
        lowered = _lower(raw_departure)
        parts = lowered.split()
        if len(parts) == 2:
            return [parts[0]], [parts[1]]
        return [lowered], []

    date_variants = [
        departure.strftime("%Y-%m-%d").lower(),
        departure.strftime("%Y/%m/%d").lower(),
        f"{departure.month}/{departure.day}/{departure.year}",
        departure.strftime("%B %d, %Y").replace(" 0", " ").lower(),
        departure.strftime("%b %d, %Y").replace(" 0", " ").lower(),
    ]
    hour_12 = departure.strftime("%I").lstrip("0") or "0"
    time_variants = [
        departure.strftime("%H:%M").lower(),
        f"{hour_12}:{departure.strftime('%M')}",
        f"{hour_12}:{departure.strftime('%M')} {departure.strftime('%p').lower()}",
        f"{hour_12}:{departure.strftime('%M')}{departure.strftime('%p').lower()}",
    ]
    return date_variants, time_variants


def _unknown_booking_details(reply_lower: str) -> list[str]:
    details = []
    for booking in BOOKINGS.values():
        if _lower(booking["passenger"]) in reply_lower:
            details.append(f"passenger {booking['passenger']}")
        if _lower(booking["route"]) in reply_lower:
            details.append(f"route {booking['route']}")
        if _lower(booking["departure"]) in reply_lower:
            details.append(f"departure {booking['departure']}")
        if _lower(booking["seat"]) in reply_lower:
            details.append(f"seat {booking['seat']}")
    seat_match = re.search(r"\bseat\s+\d{1,2}[A-F]\b", reply_lower)
    if seat_match is not None:
        details.append(f"seat assignment {seat_match.group(0)}")
    return details


def _refund_amount_evaluator(row_fields):
    expected_behavior = _row_value(row_fields, "expected_behavior")

    def evaluate(simulation_result):
        reply = _final_reply(simulation_result)
        if reply is None:
            return EvaluationResult(
                score=0.0,
                feedback=(
                    "Expected guidance that avoids inventing a refund amount, explains that the amount "
                    f"depends on fare rules or booking details, and offers to review the booking. Source "
                    f"of truth: {expected_behavior!r}. No final output was produced."
                ),
            )

        reply_lower = _lower(reply)
        invented_amount = re.search(
            r"(\$\s*\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\s*(?:dollars?|usd|%))",
            reply_lower,
        )
        mentions_dependency = "depend" in reply_lower or "based on" in reply_lower
        mentions_context = _contains_any(
            reply_lower,
            ["fare rule", "fare rules", "ticket rule", "ticket rules", "booking details", "reservation details"],
        )
        mentions_review_offer = _contains_any(
            reply_lower,
            ["confirmation code", "booking code", "reservation code"],
        )

        issues = []
        if invented_amount is not None:
            issues.append(f"wrong content: invented refund amount {invented_amount.group(0)!r}")
        if not mentions_dependency or not mentions_context:
            issues.append("missing required explanation that refund eligibility or amount depends on fare rules or booking details")
        if not mentions_review_offer:
            issues.append("missing required next step to review the booking with a confirmation code")

        if not issues:
            return EvaluationResult(
                score=1.0,
                feedback="The reply avoids a refund amount, explains the dependency on fare rules or booking details, and offers a confirmation-code review.",
            )

        return EvaluationResult(
            score=0.0,
            feedback=(
                f"Expected behavior: {expected_behavior}. Observed reply: {reply!r}. "
                f"Decisive issue: {'; '.join(issues)}."
            ),
        )

    return CodeEvaluator(
        id="refund-amount-boundary",
        description="Checks that the reply avoids invented refund amounts and gives grounded next steps.",
        evaluate=evaluate,
    )


def _booking_lookup_evaluator(row_fields):
    code = _extract_confirmation_code(_row_value(row_fields, "input"))
    expected_behavior = _row_value(row_fields, "expected_behavior")
    booking = BOOKINGS.get(code or "")

    def evaluate(simulation_result):
        if code is None or booking is None:
            return EvaluationResult(
                score=0.0,
                feedback=(
                    f"Benchmark configuration error: could not derive live booking expectations for input "
                    f"{_row_value(row_fields, 'input')!r}."
                ),
            )

        reply = _final_reply(simulation_result)
        if reply is None:
            return EvaluationResult(
                score=0.0,
                feedback=(
                    "Expected a booking summary reply with passenger, route, departure, seat, and status details "
                    f"for {code}, but no final output was produced."
                ),
            )

        reply_lower = _lower(reply)
        date_variants, time_variants = _departure_variants(booking["departure"])

        missing = []
        if _lower(booking["passenger"]) not in reply_lower:
            missing.append(f"missing passenger {booking['passenger']}")
        if _lower(booking["route"]) not in reply_lower:
            missing.append(f"missing route {booking['route']}")
        if _lower(booking["seat"]) not in reply_lower:
            missing.append(f"missing seat {booking['seat']}")
        if _lower(booking["status"]) not in reply_lower:
            missing.append(f"missing status {booking['status']}")
        if not any(option in reply_lower for option in date_variants):
            missing.append(f"missing departure date for {booking['departure']}")
        if time_variants and not any(option in reply_lower for option in time_variants):
            missing.append(f"missing departure time for {booking['departure']}")

        if not missing:
            return EvaluationResult(
                score=1.0,
                feedback="The reply summarizes the live booking details for the provided confirmation code.",
            )

        return EvaluationResult(
            score=0.0,
            feedback=(
                f"Expected behavior: {expected_behavior}. Observed reply: {reply!r}. "
                f"Decisive issue: wrong or missing booking detail(s): {', '.join(missing)}."
            ),
        )

    return CodeEvaluator(
        id="booking-lookup-details",
        description="Checks that the final reply reports the live booking details for the requested confirmation code.",
        evaluate=evaluate,
    )


def _seat_change_evaluator(row_fields):
    input_text = _row_value(row_fields, "input")
    expected_behavior = _row_value(row_fields, "expected_behavior")
    code = _extract_confirmation_code(input_text)
    seat = _extract_requested_seat(input_text)

    def evaluate(simulation_result):
        if code is None or seat is None:
            return EvaluationResult(
                score=0.0,
                feedback=f"Benchmark configuration error: could not derive seat-change expectations from input {input_text!r}.",
            )

        reply = _final_reply(simulation_result)
        if reply is None:
            return EvaluationResult(
                score=0.0,
                feedback=f"Expected a confirmation that booking {code} was changed to seat {seat}, but no final output was produced.",
            )

        reply_lower = _lower(reply)
        confirmation_terms = ["updated", "changed", "switched", "assigned", "set"]
        asks_for_code_again = "confirmation code" in reply_lower and _contains_any(
            reply_lower,
            ["please provide", "what is", "need", "share", "give me"],
        )

        issues = []
        if seat.lower() not in reply_lower:
            issues.append(f"missing required seat value {seat}")
        if not any(term in reply_lower for term in confirmation_terms):
            issues.append("missing explicit confirmation that the seat change was completed")
        if asks_for_code_again:
            issues.append(f"asked for the confirmation code again even though {code} was already provided")

        if not issues:
            return EvaluationResult(
                score=1.0,
                feedback="The reply accepts the provided confirmation code, confirms the change, and reports the requested new seat.",
            )

        return EvaluationResult(
            score=0.0,
            feedback=(
                f"Expected behavior: {expected_behavior}. Observed reply: {reply!r}. "
                f"Decisive issue: {'; '.join(issues)}."
            ),
        )

    return CodeEvaluator(
        id="seat-change-confirmation",
        description="Checks that the final reply confirms the requested seat change without re-asking for the provided confirmation code.",
        evaluate=evaluate,
    )


def _unknown_booking_evaluator(row_fields):
    expected_behavior = _row_value(row_fields, "expected_behavior")

    def evaluate(simulation_result):
        reply = _final_reply(simulation_result)
        if reply is None:
            return EvaluationResult(
                score=0.0,
                feedback="Expected a clear not-found response for the unknown booking code, but no final output was produced.",
            )

        reply_lower = _lower(reply)
        details = _unknown_booking_details(reply_lower)
        not_found = _contains_any(
            reply_lower,
            [
                "no booking was found",
                "no booking found",
                "not found",
                "could not find",
                "couldn't find",
                "can't find",
                "cannot find",
            ],
        )

        issues = []
        if not not_found:
            issues.append("missing required not-found message for the unknown confirmation code")
        if details:
            issues.append(f"wrong content: included booking-specific detail(s) {', '.join(details)}")

        if not issues:
            return EvaluationResult(
                score=1.0,
                feedback="The reply clearly reports that the booking was not found and avoids booking-specific fabrication.",
            )

        return EvaluationResult(
            score=0.0,
            feedback=(
                f"Expected behavior: {expected_behavior}. Observed reply: {reply!r}. "
                f"Decisive issue: {'; '.join(issues)}."
            ),
        )

    return CodeEvaluator(
        id="unknown-booking-not-found",
        description="Checks that the final reply reports an unknown booking code without inventing booking details.",
        evaluate=evaluate,
    )


def _build_evaluators(row_fields):
    sample_id = _row_value(row_fields, "sample_id")
    if sample_id == "refund-amount-boundary":
        return [_refund_amount_evaluator(row_fields)]
    if sample_id == "booking-lookup-sky123":
        return [_booking_lookup_evaluator(row_fields)]
    if sample_id == "seat-change-sky123":
        return [_seat_change_evaluator(row_fields)]
    if sample_id == "unknown-booking-code":
        return [_unknown_booking_evaluator(row_fields)]
    return [
        CodeEvaluator(
            id="unsupported-row",
            description="Fails fast when the benchmark CSV includes an unexpected sample identifier.",
            evaluate=lambda simulation_result: EvaluationResult(
                score=0.0,
                feedback=f"Benchmark configuration error: unsupported sample_id {sample_id!r}.",
            ),
        )
    ]


def _row_name(row_fields) -> str:
    sample_id = _row_value(row_fields, "sample_id")
    names = {
        "refund-amount-boundary": "Refund Amount Boundary",
        "booking-lookup-sky123": "Booking Lookup SKY123",
        "seat-change-sky123": "Seat Change SKY123",
        "unknown-booking-code": "Unknown Booking Code",
    }
    return names.get(sample_id, sample_id.replace("-", " ").title())


def _row_description(row_fields) -> str:
    sample_id = _row_value(row_fields, "sample_id")
    descriptions = {
        "refund-amount-boundary": "Checks that refund guidance stays grounded instead of inventing an amount.",
        "booking-lookup-sky123": "Checks that the agent summarizes the live SKY123 booking details.",
        "seat-change-sky123": "Checks that the agent confirms the requested SKY123 seat change.",
        "unknown-booking-code": "Checks that the agent reports an unknown booking code without fabricating details.",
    }
    return descriptions.get(sample_id, _row_value(row_fields, "expected_behavior"))


def build_environment(row_fields, sample_index):
    sample_id = _row_value(row_fields, "sample_id") or f"sample-{sample_index}"
    return RELAIEnvironment(
        schema_version="relai.learning_environment.v1",
        id=sample_id,
        name=_row_name(row_fields),
        description=_row_description(row_fields),
        tags=["end-to-end"],
        target=AgentTarget(),
        input=FixedInput(
            turns=[
                FixedTurn(content=_row_value(row_fields, "input")),
            ]
        ),
        mocks={
            "airline_support.agent:change_seat": mock_change_seat,
        },
        evaluators=_build_evaluators(row_fields),
    )


benchmark = RELAIBenchmark(
    schema_version="relai.benchmark.v1",
    id=BENCHMARK_ID,
    name=BENCHMARK_NAME,
    description="Exercises the airline support agent on refund boundaries, booking lookup, seat changes, and unknown booking handling.",
    dataset_ref=StoredBenchmarkCsv(id=DATASET_REF_ID),
    required_columns=REQUIRED_COLUMNS,
    build_environment=build_environment,
)
