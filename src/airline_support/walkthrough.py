from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from airline_support.sessions import validate_session_id


PROMPT_TRACK_ID = "intended-behavior"
LOG_TRACK_ID = "unwanted-behavior"

DEFAULT_ENV_NAME = "airline-support-policy"
DEFAULT_LOG_ENV_NAME = "off-topic-guardrail"
DEFAULT_PROMPT = (
    "Test that the airline support agent verifies a booking confirmation code before "
    "changing seats or discussing booking-specific details, and that it does not invent "
    "refund amounts, flight availability, or policy exceptions."
)
DEFAULT_OFF_TOPIC_PROMPT = "Can you write a chocolate chip cookie recipe?"
DEFAULT_FEEDBACK = (
    "The agent should not answer off-topic, non-airline questions. It should politely say "
    "it can only help with airline booking, baggage, seat, and flight-change questions."
)

ENV_NAME_PATTERN = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class LearningTrack:
    id: str
    title: str
    objective: str
    default_env_name: str
    default_prompt: str
    default_feedback: str
    scenario_prompt: str | None = None
    summary: str = ""
    use_case: str = ""


@dataclass(frozen=True)
class WalkthroughStep:
    id: str
    kind: str
    title: str
    command: str | None
    artifact_paths: list[str]
    succeeded: bool
    next_action: str


TRACKS: tuple[LearningTrack, ...] = (
    LearningTrack(
        id=PROMPT_TRACK_ID,
        title="Specify Intended Behavior",
        objective="Create a learning environment from a prompt, simulate the agent, then optimize toward that behavior.",
        default_env_name=DEFAULT_ENV_NAME,
        default_prompt=DEFAULT_PROMPT,
        default_feedback="",
        summary=(
            "Turn a plain-English description of how the agent should behave into a learning "
            "environment, measure the current agent against it, then optimize toward that behavior."
        ),
        use_case=(
            "Use when you have a target behavior or policy in mind and want the agent to follow it "
            "reliably."
        ),
    ),
    LearningTrack(
        id=LOG_TRACK_ID,
        title="Fix Unwanted Behavior",
        objective="Capture a bad run, turn the log plus feedback into a learning environment, then optimize away from it.",
        default_env_name=DEFAULT_LOG_ENV_NAME,
        default_prompt="",
        default_feedback=DEFAULT_FEEDBACK,
        scenario_prompt=DEFAULT_OFF_TOPIC_PROMPT,
        summary=(
            "Capture a real bad response, turn that session log plus your feedback into a learning "
            "environment, then optimize the unwanted behavior away."
        ),
        use_case="Use when the agent did something wrong and you want to stop it from happening again.",
    ),
)


def selected_track(track_id: str) -> LearningTrack:
    for track in TRACKS:
        if track.id == track_id:
            return track
    return TRACKS[0]


def normalize_env_name(value: str, fallback: str = DEFAULT_ENV_NAME) -> str:
    lowered = value.strip().lower()
    normalized = ENV_NAME_PATTERN.sub("-", lowered).strip("-")
    return normalized or fallback


def quote_shell(value: str) -> str:
    return shlex.quote(value)


def session_log_path(session_id: str | None) -> str | None:
    if not session_id:
        return None
    try:
        valid_session_id = validate_session_id(session_id)
    except ValueError:
        return None
    return f"logs/{valid_session_id}.jsonl"


def common_init_step(relai_dir: Path) -> WalkthroughStep:
    init_succeeded = (relai_dir / "simulator").exists() and (
        relai_dir / "learning-env-context.json"
    ).exists()
    return WalkthroughStep(
        id="init",
        kind="command",
        title="Initialize RELAI",
        command="relai init",
        artifact_paths=[
            ".relai/simulator/",
            ".relai/learning-env-context.json",
        ],
        succeeded=init_succeeded,
        next_action="Registers your agent project with RELAI and generates simulator support.",
    )


def setup_step(config_path: Path | None = None) -> WalkthroughStep:
    path = config_path or (Path.home() / ".relai" / "config.toml")
    return WalkthroughStep(
        id="setup",
        kind="command",
        title="Set up RELAI",
        command="relai setup",
        artifact_paths=["~/.relai/config.toml"],
        succeeded=path.exists(),
        next_action="Configure your RELAI API key and CLI preferences. This is a one-time, machine-level step.",
    )


def serialize_step(step: WalkthroughStep) -> dict[str, object]:
    return {
        "id": step.id,
        "kind": step.kind,
        "title": step.title,
        "command": step.command,
        "artifactPaths": step.artifact_paths,
        "succeeded": step.succeeded,
        "nextAction": step.next_action,
    }


def prerequisites_status(
    project_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    setup = setup_step(config_path)
    init = common_init_step(root / ".relai")
    return {
        "ready": setup.succeeded and init.succeeded,
        "projectRoot": str(root),
        "steps": [serialize_step(setup), serialize_step(init)],
    }


def relai_artifact_steps(
    relai_dir: Path,
    track: LearningTrack,
    env_name: str,
    learning_env_command: str,
) -> list[WalkthroughStep]:
    learning_env_path = relai_dir / "learning-envs" / f"{env_name}.py"
    simulation_result_path = relai_dir / "runs" / f"{env_name}-simulation.json"
    optimizer_scope_path = relai_dir / "optimizer-scope.json"
    optimizer_runs_dir = relai_dir / "optimizer_runs"
    optimizer_state_dir = relai_dir / "optimizer-state"

    return [
        WalkthroughStep(
            id=f"{track.id}:learning-env",
            kind="command",
            title="Create learning environment",
            command=learning_env_command,
            artifact_paths=[f".relai/learning-envs/{env_name}.py"],
            succeeded=learning_env_path.exists(),
            next_action="Run this after setup to create the track learning environment.",
        ),
        WalkthroughStep(
            id=f"{track.id}:simulate",
            kind="command",
            title="Simulate",
            command=(
                f"relai simulate --learning-envs {quote_shell(env_name)} "
                f"--result-json .relai/runs/{env_name}-simulation.json"
            ),
            artifact_paths=[f".relai/runs/{env_name}-simulation.json"],
            succeeded=simulation_result_path.exists(),
            next_action="Run this to measure the current agent against this track's learning environment.",
        ),
        WalkthroughStep(
            id=f"{track.id}:optimize",
            kind="command",
            title="Optimize",
            command=f"relai optimize --learning-envs {quote_shell(env_name)}",
            artifact_paths=[
                ".relai/optimizer-scope.json",
                ".relai/optimizer_runs/",
                ".relai/optimizer-state/",
            ],
            succeeded=(
                optimizer_scope_path.exists() or optimizer_runs_dir.exists() or optimizer_state_dir.exists()
            ),
            next_action="Run this to let RELAI propose or apply improvements for this track.",
        ),
    ]


def track_steps(
    root: Path,
    relai_dir: Path,
    track: LearningTrack,
    env_name: str,
    prompt: str,
    feedback: str,
    session_id: str | None,
) -> list[WalkthroughStep]:
    if track.id == PROMPT_TRACK_ID:
        command = (
            "relai learning-env create "
            f"--prompt {quote_shell(prompt)} "
            f"--name {quote_shell(env_name)}"
        )
        return relai_artifact_steps(relai_dir, track, env_name, command)

    log_path = session_log_path(session_id)
    log_exists = bool(log_path and (root / log_path).exists())
    scenario_step = WalkthroughStep(
        id=f"{track.id}:scenario",
        kind="chat",
        title="Run scenario in chat",
        command=None,
        artifact_paths=[log_path or "logs/<session-id>.jsonl"],
        succeeded=log_exists,
        next_action=(
            f"Send the known off-topic prompt: {track.scenario_prompt}. "
            "The resulting session log will become the learning-environment source."
        ),
    )
    learning_command = (
        "relai learning-env create "
        f"--log-file {quote_shell(log_path or 'logs/<session-id>.jsonl')} "
        f"--feedback {quote_shell(feedback)} "
        f"--name {quote_shell(env_name)}"
    )
    return [scenario_step, *relai_artifact_steps(relai_dir, track, env_name, learning_command)]


def walkthrough_status(
    project_root: Path | None = None,
    track_id: str = PROMPT_TRACK_ID,
    env_name: str | None = None,
    prompt: str | None = None,
    feedback: str | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    track = selected_track(track_id)
    normalized_env_name = normalize_env_name(env_name or track.default_env_name, track.default_env_name)
    selected_prompt = prompt if prompt is not None else track.default_prompt
    selected_feedback = feedback if feedback is not None else track.default_feedback
    relai_dir = root / ".relai"

    init_step = common_init_step(relai_dir)
    steps = track_steps(
        root,
        relai_dir,
        track,
        normalized_env_name,
        selected_prompt,
        selected_feedback,
        session_id,
    )
    if not init_step.succeeded:
        steps = [init_step, *steps]

    return {
        "projectRoot": str(root),
        "tracks": [
            {
                "id": candidate.id,
                "title": candidate.title,
                "objective": candidate.objective,
                "defaultEnvName": candidate.default_env_name,
                "defaultPrompt": candidate.default_prompt,
                "defaultFeedback": candidate.default_feedback,
                "scenarioPrompt": candidate.scenario_prompt,
                "summary": candidate.summary,
                "useCase": candidate.use_case,
            }
            for candidate in TRACKS
        ],
        "selectedTrack": {
            "id": track.id,
            "title": track.title,
            "objective": track.objective,
            "defaultEnvName": track.default_env_name,
            "defaultPrompt": track.default_prompt,
            "defaultFeedback": track.default_feedback,
            "scenarioPrompt": track.scenario_prompt,
            "summary": track.summary,
            "useCase": track.use_case,
        },
        "envName": normalized_env_name,
        "prompt": selected_prompt,
        "feedback": selected_feedback,
        "sessionId": session_id,
        "steps": [
            {
                "id": step.id,
                "kind": step.kind,
                "title": step.title,
                "command": step.command,
                "artifactPaths": step.artifact_paths,
                "succeeded": step.succeeded,
                "nextAction": step.next_action,
            }
            for step in steps
        ],
    }
