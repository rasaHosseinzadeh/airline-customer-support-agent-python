
from __future__ import annotations

import re

from relai import CodeEvaluator, EvaluationResult, SimulationResult

try:
    import tiktoken
except ImportError:
    tiktoken = None


MAX_RESPONSE_TOKENS = 100
FALLBACK_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _get_response_text(simulation_result: SimulationResult) -> str:
    final_output = simulation_result.final_output
    if final_output is None:
        return ""
    return str(final_output).strip()


def _count_tokens(text: str) -> int:
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            pass

    return len(FALLBACK_TOKEN_PATTERN.findall(text))


def evaluate(simulation_result: SimulationResult) -> EvaluationResult:
    response_text = _get_response_text(simulation_result)
    if not response_text:
        return EvaluationResult(
            score=0.0,
            feedback="The agent did not return a final assistant reply to measure against the 100-token limit.",
        )

    token_count = _count_tokens(response_text)
    if token_count <= MAX_RESPONSE_TOKENS:
        return EvaluationResult(
            score=1.0,
            feedback=f"The final assistant reply is {token_count} tokens long, within the 100-token limit.",
        )

    return EvaluationResult(
        score=0.0,
        feedback=(
            f"The final assistant reply is {token_count} tokens long, exceeding the "
            f"100-token limit by {token_count - MAX_RESPONSE_TOKENS} tokens."
        ),
    )


evaluator = CodeEvaluator(
    id="response-token",
    scope="end-to-end",
    description="Checks whether the final assistant reply stays within a 100-token limit.",
    evaluate=evaluate,
)
