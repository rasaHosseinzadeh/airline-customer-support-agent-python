from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from airline_support.sessions import validate_session_id


PROMPT_TRACK_ID = "intended-behavior"
LOG_TRACK_ID = "unwanted-behavior"
BENCHMARK_TRACK_ID = "benchmark"
GLOBAL_EVALUATOR_TRACK_ID = "global-evaluator"

PROMPT_TRACK_KIND = "prompt-learning-env"
LOG_TRACK_KIND = "log-feedback-learning-env"
BENCHMARK_TRACK_KIND = "benchmark"
GLOBAL_EVALUATOR_TRACK_KIND = "global-evaluator"

DEFAULT_ENV_NAME = "response-signoff"
DEFAULT_LOG_ENV_NAME = "off-topic-guardrail"
DEFAULT_BENCHMARK_NAME = "airline-support-suite"
DEFAULT_GLOBAL_EVALUATOR_NAME = "response-token"
DEFAULT_GLOBAL_EVALUATOR_ENV_NAME = "response-token-smoke-test"
GLOBAL_EVALUATOR_RESULT_SUFFIX = "global-evaluator-simulation"

DEFAULT_PROMPT = (
    "The agent should end all responses with "
    "'please let me know if you have any questions'."
)
DEFAULT_OFF_TOPIC_PROMPT = "Can you write a chocolate chip cookie recipe?"
DEFAULT_FEEDBACK = (
    "The agent should not answer off-topic, non-airline questions. It should politely say "
    "it can only help with airline booking, baggage, seat, and flight-change questions."
)
DEFAULT_GLOBAL_EVALUATOR_PROMPT = (
    "Create an evaluator that scores 1 when an agent response is 100 tokens or fewer, "
    "and scores 0 otherwise."
)

ENV_NAME_PATTERN = re.compile(r"[^a-z0-9-]+")
SHELL_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")


@dataclass(frozen=True)
class LearningTrack:
    id: str
    kind: str
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


@dataclass(frozen=True)
class SimulationTarget:
    kind: str
    name: str
    artifact_path: Path
    relai_path: str
    simulate_flag: str


TRACKS: tuple[LearningTrack, ...] = (
    LearningTrack(
        id=PROMPT_TRACK_ID,
        kind=PROMPT_TRACK_KIND,
        title="Learning Environment from Prompt",
        objective=(
            "Turn one simple plain-English behavior prompt into a learning environment, measure "
            "the current agent against it, then optimize toward that behavior. Use this when you "
            "have a target behavior in mind and want the agent to follow it reliably."
        ),
        default_env_name=DEFAULT_ENV_NAME,
        default_prompt=DEFAULT_PROMPT,
        default_feedback="",
        summary=(
            "Turn one simple plain-English behavior prompt into a learning environment, measure "
            "the current agent against it, then optimize toward that behavior."
        ),
        use_case=(
            "Use when you have a target behavior in mind and want the agent to follow it reliably."
        ),
    ),
    LearningTrack(
        id=LOG_TRACK_ID,
        kind=LOG_TRACK_KIND,
        title="Learning Environment from Log + Feedback",
        objective=(
            "Capture a real, undesirable behavior in a session log, then turn that log plus your "
            "feedback into a learning environment and optimize the unwanted behavior away. Use this "
            "when the agent did something wrong and you want to stop it from happening again."
        ),
        default_env_name=DEFAULT_LOG_ENV_NAME,
        default_prompt="",
        default_feedback=DEFAULT_FEEDBACK,
        scenario_prompt=DEFAULT_OFF_TOPIC_PROMPT,
        summary=(
            "Capture a real, undesirable behavior in a session log, then turn that log plus your "
            "feedback into a learning environment and optimize the unwanted behavior away."
        ),
        use_case="Use when the agent did something wrong and you want to stop it from happening again.",
    ),
    LearningTrack(
        id=BENCHMARK_TRACK_ID,
        kind=BENCHMARK_TRACK_KIND,
        title="Benchmark",
        objective=(
            "Register a reusable benchmark in CSV format, then run simulation and optimization "
            "against it. Use this when you have a set of samples, each with inputs, expected "
            "outputs, and sample-specific evaluators, that should be rerun together."
        ),
        default_env_name=DEFAULT_BENCHMARK_NAME,
        default_prompt="",
        default_feedback="",
        summary=(
            "Register a reusable benchmark in CSV format, then run simulation and optimization "
            "against it."
        ),
        use_case=(
            "Use when you have a set of samples, each with inputs, expected outputs, and "
            "sample-specific evaluators, that should be rerun together."
        ),
    ),
    LearningTrack(
        id=GLOBAL_EVALUATOR_TRACK_ID,
        kind=GLOBAL_EVALUATOR_TRACK_KIND,
        title="Global Evaluators",
        objective=(
            "Create one evaluator that applies across all simulations for the agent. Use this when "
            "one scoring rule should apply globally instead of living in a single learning "
            "environment."
        ),
        default_env_name=DEFAULT_GLOBAL_EVALUATOR_ENV_NAME,
        default_prompt=DEFAULT_GLOBAL_EVALUATOR_PROMPT,
        default_feedback="",
        summary=(
            "Create one evaluator that applies across all simulations for the agent."
        ),
        use_case=(
            "Use when one scoring rule should apply globally instead of living in a single "
            "learning environment."
        ),
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
    if value and SHELL_SAFE_TOKEN_PATTERN.fullmatch(value):
        return value
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )
    return f'"{escaped}"'


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


def install_cli_step() -> WalkthroughStep:
    relai_path = shutil.which("relai")
    return WalkthroughStep(
        id="install-cli",
        kind="command",
        title="Install RELAI CLI",
        command="uv tool install relai",
        artifact_paths=["relai on PATH"],
        succeeded=relai_path is not None,
        next_action="Install the RELAI CLI locally so the setup and project commands can run.",
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


def serialize_track(track: LearningTrack) -> dict[str, object]:
    return {
        "id": track.id,
        "kind": track.kind,
        "title": track.title,
        "objective": track.objective,
        "defaultEnvName": track.default_env_name,
        "defaultPrompt": track.default_prompt,
        "defaultFeedback": track.default_feedback,
        "scenarioPrompt": track.scenario_prompt,
        "summary": track.summary,
        "useCase": track.use_case,
    }


def normalize_relai_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    if "/.relai/" in normalized:
        normalized = normalized.split("/.relai/", 1)[1]
        return f"relai/{normalized}".rstrip("/")
    return normalized.lstrip("./").rstrip("/")


def iter_json_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_json_strings(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from iter_json_strings(item)


def json_file_references_path(path: Path, target_paths: set[str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    try:
        payloads = [json.loads(text)]
    except json.JSONDecodeError:
        payloads = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                payloads.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return any(
        normalize_relai_path(value) in target_paths
        for payload in payloads
        for value in iter_json_strings(payload)
    )


def optimizer_succeeded_for_targets(relai_dir: Path, target_paths: list[str]) -> bool:
    normalized_targets = {normalize_relai_path(path) for path in target_paths}
    optimizer_state_dir = relai_dir / "optimizer-state"
    optimizer_runs_dir = relai_dir / "optimizer_runs"
    candidate_files = [relai_dir / "optimizer-scope.json"]
    if optimizer_state_dir.exists():
        candidate_files.extend(optimizer_state_dir.rglob("*.json"))
    if optimizer_runs_dir.exists():
        candidate_files.extend(optimizer_runs_dir.rglob("*.json"))
        candidate_files.extend(optimizer_runs_dir.rglob("*.jsonl"))
    return any(json_file_references_path(path, normalized_targets) for path in candidate_files)


def prerequisites_status(
    project_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    setup = setup_step(config_path)
    init = common_init_step(root / ".relai")
    install_cli = install_cli_step()
    return {
        "ready": install_cli.succeeded and setup.succeeded and init.succeeded,
        "projectRoot": str(root),
        "steps": [serialize_step(install_cli), serialize_step(setup), serialize_step(init)],
    }


def relai_artifact_steps(
    relai_dir: Path,
    track: LearningTrack,
    env_name: str,
    learning_env_command: str,
) -> list[WalkthroughStep]:
    learning_env_path = relai_dir / "learning-envs" / f"{env_name}.py"
    simulation_result_path = relai_dir / "runs" / f"{env_name}-simulation.json"
    learning_env_relai_path = f".relai/learning-envs/{env_name}.py"
    simulation_result_relai_path = f".relai/runs/{env_name}-simulation.json"

    return [
        WalkthroughStep(
            id=f"{track.id}:learning-env",
            kind="command",
            title="Create learning environment",
            command=learning_env_command,
            artifact_paths=[learning_env_relai_path],
            succeeded=learning_env_path.exists(),
            next_action="Run this after setup to create the loop learning environment.",
        ),
        WalkthroughStep(
            id=f"{track.id}:simulate",
            kind="command",
            title="Simulate",
            command=(
                f"relai simulate --learning-envs {quote_shell(env_name)} "
                f"--result-json {simulation_result_relai_path}"
            ),
            artifact_paths=[simulation_result_relai_path],
            succeeded=simulation_result_path.exists(),
            next_action="Run this to measure the current agent against this loop's learning environment.",
        ),
        WalkthroughStep(
            id=f"{track.id}:optimize",
            kind="command",
            title="Optimize",
            command="relai optimize",
            artifact_paths=[
                ".relai/optimizer-scope.json",
                ".relai/optimizer_runs/",
                ".relai/optimizer-state/",
            ],
            succeeded=optimizer_succeeded_for_targets(
                relai_dir,
                [learning_env_relai_path, simulation_result_relai_path],
            ),
            next_action="Run this to let RELAI propose or apply improvements for this loop.",
        ),
    ]


def benchmark_artifact_steps(
    relai_dir: Path,
    track: LearningTrack,
    benchmark_name: str,
) -> list[WalkthroughStep]:
    benchmark_path = relai_dir / "benchmarks" / f"{benchmark_name}.py"
    simulation_result_path = relai_dir / "runs" / f"{benchmark_name}-simulation.json"
    benchmark_relai_path = f".relai/benchmarks/{benchmark_name}.py"
    simulation_result_relai_path = f".relai/runs/{benchmark_name}-simulation.json"

    return [
        WalkthroughStep(
            id=f"{track.id}:register",
            kind="command",
            title="Register benchmark",
            command=(
                "relai benchmark register "
                "--csv benchmarks/airline_support_benchmark.csv "
                f"--name {quote_shell(benchmark_name)}"
            ),
            artifact_paths=[benchmark_relai_path],
            succeeded=benchmark_path.exists(),
            next_action="Run this to register the CSV benchmark with RELAI.",
        ),
        WalkthroughStep(
            id=f"{track.id}:simulate",
            kind="command",
            title="Simulate",
            command=(
                f"relai simulate --benchmarks {quote_shell(benchmark_name)} "
                f"--result-json {simulation_result_relai_path}"
            ),
            artifact_paths=[simulation_result_relai_path],
            succeeded=simulation_result_path.exists(),
            next_action="Run this to measure the current agent against the registered benchmark.",
        ),
        WalkthroughStep(
            id=f"{track.id}:optimize",
            kind="command",
            title="Optimize",
            command="relai optimize",
            artifact_paths=[
                ".relai/optimizer-scope.json",
                ".relai/optimizer_runs/",
                ".relai/optimizer-state/",
            ],
            succeeded=optimizer_succeeded_for_targets(
                relai_dir,
                [benchmark_relai_path, simulation_result_relai_path],
            ),
            next_action="Run this to let RELAI propose or apply improvements using the benchmark.",
        ),
    ]


def global_evaluator_targets(relai_dir: Path) -> list[SimulationTarget]:
    return [
        SimulationTarget(
            kind="learning environment",
            name=DEFAULT_ENV_NAME,
            artifact_path=relai_dir / "learning-envs" / f"{DEFAULT_ENV_NAME}.py",
            relai_path=f".relai/learning-envs/{DEFAULT_ENV_NAME}.py",
            simulate_flag="--learning-envs",
        ),
        SimulationTarget(
            kind="learning environment",
            name=DEFAULT_LOG_ENV_NAME,
            artifact_path=relai_dir / "learning-envs" / f"{DEFAULT_LOG_ENV_NAME}.py",
            relai_path=f".relai/learning-envs/{DEFAULT_LOG_ENV_NAME}.py",
            simulate_flag="--learning-envs",
        ),
        SimulationTarget(
            kind="benchmark",
            name=DEFAULT_BENCHMARK_NAME,
            artifact_path=relai_dir / "benchmarks" / f"{DEFAULT_BENCHMARK_NAME}.py",
            relai_path=f".relai/benchmarks/{DEFAULT_BENCHMARK_NAME}.py",
            simulate_flag="--benchmarks",
        ),
    ]


def selected_global_evaluator_target(relai_dir: Path) -> SimulationTarget | None:
    return next(
        (target for target in global_evaluator_targets(relai_dir) if target.artifact_path.exists()),
        None,
    )


def global_evaluator_result_path(target: SimulationTarget) -> str:
    return f".relai/runs/{target.name}-{GLOBAL_EVALUATOR_RESULT_SUFFIX}.json"


def global_evaluator_steps(
    relai_dir: Path,
    track: LearningTrack,
    evaluator_prompt: str,
) -> list[WalkthroughStep]:
    evaluator_path = relai_dir / "evaluators" / f"{DEFAULT_GLOBAL_EVALUATOR_NAME}.py"
    evaluator_relai_path = f".relai/evaluators/{DEFAULT_GLOBAL_EVALUATOR_NAME}.py"
    target = selected_global_evaluator_target(relai_dir)

    if target is None:
        return [
            WalkthroughStep(
                id=f"{track.id}:source",
                kind="command",
                title="Finish another loop first",
                command=None,
                artifact_paths=[target.relai_path for target in global_evaluator_targets(relai_dir)],
                succeeded=False,
                next_action=(
                    "Finish Learning Environment (Prompt), Learning Environment (Log), or Benchmark first "
                    "so there is something to simulate. Once one exists, this loop will show a simulation "
                    "command for it."
                ),
            )
        ]

    simulation_result_relai_path = global_evaluator_result_path(target)
    simulation_result_path = relai_dir.parent / simulation_result_relai_path

    return [
        WalkthroughStep(
            id=f"{track.id}:evaluator",
            kind="command",
            title="Create global evaluator",
            command=(
                "relai evaluator create "
                f"--prompt {quote_shell(evaluator_prompt)} "
                f"--name {quote_shell(DEFAULT_GLOBAL_EVALUATOR_NAME)}"
            ),
            artifact_paths=[evaluator_relai_path],
            succeeded=evaluator_path.exists(),
            next_action="Run this to create the global response-token evaluator.",
        ),
        WalkthroughStep(
            id=f"{track.id}:simulate",
            kind="command",
            title="Simulate with global evaluator",
            command=(
                f"relai simulate {target.simulate_flag} {quote_shell(target.name)} "
                f"--result-json {simulation_result_relai_path}"
            ),
            artifact_paths=[simulation_result_relai_path],
            succeeded=simulation_result_path.exists(),
            next_action=(
                f"Run this against the detected {target.kind} `{target.name}`. RELAI applies the global "
                "evaluator automatically after it has been created."
            ),
        ),
        WalkthroughStep(
            id=f"{track.id}:optimize",
            kind="command",
            title="Optimize",
            command="relai optimize",
            artifact_paths=[
                ".relai/optimizer-scope.json",
                ".relai/optimizer_runs/",
                ".relai/optimizer-state/",
            ],
            succeeded=optimizer_succeeded_for_targets(
                relai_dir,
                [target.relai_path, evaluator_relai_path, simulation_result_relai_path],
            ),
            next_action="Run this to let RELAI propose or apply improvements with the global evaluator active.",
        ),
    ]


def delete_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def reset_track_outputs(
    project_root: Path | None = None,
    track_id: str = PROMPT_TRACK_ID,
    env_name: str | None = None,
) -> dict[str, object]:
    root = (project_root or Path.cwd()).resolve()
    track = selected_track(track_id)
    normalized_env_name = normalize_env_name(
        env_name or track.default_env_name,
        track.default_env_name,
    )
    relai_dir = root / ".relai"
    paths: list[Path] = [
        relai_dir / "optimizer-scope.json",
        relai_dir / "optimizer_runs",
        relai_dir / "optimizer-state",
    ]

    if track.kind != GLOBAL_EVALUATOR_TRACK_KIND:
        paths.append(relai_dir / "runs" / f"{normalized_env_name}-simulation.json")

    if track.kind in {PROMPT_TRACK_KIND, LOG_TRACK_KIND}:
        paths.append(relai_dir / "learning-envs" / f"{normalized_env_name}.py")

    if track.kind == BENCHMARK_TRACK_KIND:
        paths.extend(
            [
                relai_dir / "benchmarks" / f"{normalized_env_name}.py",
                relai_dir / "benchmarks" / f"{normalized_env_name}.csv",
                relai_dir / "benchmarks" / normalized_env_name,
            ]
        )

    if track.kind == GLOBAL_EVALUATOR_TRACK_KIND:
        paths.append(relai_dir / "evaluators" / f"{DEFAULT_GLOBAL_EVALUATOR_NAME}.py")
        paths.append(relai_dir / "learning-envs" / f"{DEFAULT_GLOBAL_EVALUATOR_ENV_NAME}.py")
        paths.append(relai_dir / "runs" / f"{DEFAULT_GLOBAL_EVALUATOR_ENV_NAME}-simulation.json")
        paths.extend(
            relai_dir / "runs" / f"{target.name}-{GLOBAL_EVALUATOR_RESULT_SUFFIX}.json"
            for target in global_evaluator_targets(relai_dir)
        )

    deleted = [str(path.relative_to(root)) for path in paths if delete_path(path)]
    return {
        "trackId": track.id,
        "envName": normalized_env_name,
        "deleted": deleted,
    }


def track_steps(
    root: Path,
    relai_dir: Path,
    track: LearningTrack,
    env_name: str,
    prompt: str,
    feedback: str,
    session_id: str | None,
) -> list[WalkthroughStep]:
    if track.kind == PROMPT_TRACK_KIND:
        command = (
            "relai learning-env create "
            f"--prompt {quote_shell(prompt)} "
            f"--name {quote_shell(env_name)}"
        )
        return relai_artifact_steps(relai_dir, track, env_name, command)

    if track.kind == BENCHMARK_TRACK_KIND:
        return benchmark_artifact_steps(relai_dir, track, env_name)

    if track.kind == GLOBAL_EVALUATOR_TRACK_KIND:
        return global_evaluator_steps(relai_dir, track, prompt)

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
    normalized_env_name = normalize_env_name(
        env_name or track.default_env_name,
        track.default_env_name,
    )
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
        "tracks": [serialize_track(candidate) for candidate in TRACKS],
        "selectedTrack": serialize_track(track),
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
