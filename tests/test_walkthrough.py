from __future__ import annotations

import csv
from pathlib import Path

from airline_support.walkthrough import (
    BENCHMARK_TRACK_ID,
    GLOBAL_EVALUATOR_TRACK_ID,
    LOG_TRACK_ID,
    normalize_env_name,
    prerequisites_status,
    reset_track_outputs,
    walkthrough_status,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_prompt_track_commands_and_artifacts(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "response-signoff.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "response-signoff-simulation.json").write_text("{}", encoding="utf-8")

    status = walkthrough_status(project_root=tmp_path)
    steps = {step["id"]: step for step in status["steps"]}

    assert status["selectedTrack"]["id"] == "intended-behavior"
    assert status["selectedTrack"]["kind"] == "prompt-learning-env"
    assert [track["id"] for track in status["tracks"]] == [
        "intended-behavior",
        "unwanted-behavior",
        "benchmark",
        "global-evaluator",
    ]
    assert status["prompt"] == "The agent should end all responses with 'please let me know if you have any questions'."
    assert "init" not in steps
    assert steps["intended-behavior:learning-env"]["succeeded"] is True
    assert steps["intended-behavior:simulate"]["succeeded"] is True
    expected_command = (
        'relai learning-env create --prompt "The agent should end all responses with '
        "'please let me know if you have any questions'." '" --name response-signoff'
    )
    assert (
        steps["intended-behavior:learning-env"]["command"]
        == expected_command
    )
    assert "'\"'\"'" not in steps["intended-behavior:learning-env"]["command"]


def test_init_step_is_shared_when_relai_is_not_initialized(tmp_path):
    status = walkthrough_status(project_root=tmp_path)

    assert status["steps"][0]["id"] == "init"
    assert status["steps"][0]["command"] == "relai init"


def test_log_feedback_track_uses_session_log_and_feedback(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "session-abc12345.jsonl").write_text("{}", encoding="utf-8")

    status = walkthrough_status(
        project_root=tmp_path,
        track_id=LOG_TRACK_ID,
        session_id="session-abc12345",
    )
    steps = {step["id"]: step for step in status["steps"]}

    assert status["envName"] == "off-topic-guardrail"
    assert steps["unwanted-behavior:scenario"]["succeeded"] is True
    command = steps["unwanted-behavior:learning-env"]["command"]
    assert "--log-file logs/session-abc12345.jsonl" in command
    assert "--feedback" in command
    assert "--name off-topic-guardrail" in command


def test_log_track_artifacts_use_track_env_name(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "off-topic-guardrail.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "off-topic-guardrail-simulation.json").write_text("{}", encoding="utf-8")

    status = walkthrough_status(project_root=tmp_path, track_id=LOG_TRACK_ID)
    steps = {step["id"]: step for step in status["steps"]}

    assert steps["unwanted-behavior:learning-env"]["succeeded"] is True
    assert steps["unwanted-behavior:simulate"]["succeeded"] is True


def test_optimizer_detection_is_scoped_to_selected_learning_env(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "optimizer-state").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "response-signoff.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "response-signoff-simulation.json").write_text("{}", encoding="utf-8")
    (relai_dir / "optimizer-scope.json").write_text("{}", encoding="utf-8")
    (relai_dir / "optimizer-state" / "meta.json").write_text(
        '{"discovered_environment_paths":[".relai/learning-envs/off-topic-guardrail.py"]}',
        encoding="utf-8",
    )

    status = walkthrough_status(project_root=tmp_path)
    steps = {step["id"]: step for step in status["steps"]}

    assert steps["intended-behavior:optimize"]["succeeded"] is False


def test_optimizer_detection_accepts_current_learning_env_reference(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "optimizer-state").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "response-signoff.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "response-signoff-simulation.json").write_text("{}", encoding="utf-8")
    (relai_dir / "optimizer-state" / "meta.json").write_text(
        '{"discovered_environment_paths":[".relai/learning-envs/response-signoff.py"]}',
        encoding="utf-8",
    )

    status = walkthrough_status(project_root=tmp_path)
    steps = {step["id"]: step for step in status["steps"]}

    assert steps["intended-behavior:optimize"]["succeeded"] is True


def test_benchmark_track_commands_and_artifacts(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "benchmarks").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "benchmarks" / "airline-support-suite.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "airline-support-suite-simulation.json").write_text("{}", encoding="utf-8")

    status = walkthrough_status(project_root=tmp_path, track_id=BENCHMARK_TRACK_ID)
    steps = {step["id"]: step for step in status["steps"]}

    assert status["selectedTrack"]["kind"] == "benchmark"
    assert status["envName"] == "airline-support-suite"
    assert steps["benchmark:register"]["succeeded"] is True
    assert steps["benchmark:simulate"]["succeeded"] is True
    assert "relai benchmark register" in steps["benchmark:register"]["command"]
    assert "--csv benchmarks/airline_support_benchmark.csv" in steps["benchmark:register"]["command"]
    assert "--name airline-support-suite" in steps["benchmark:register"]["command"]
    assert steps["benchmark:simulate"]["command"].startswith("relai simulate --benchmarks airline-support-suite")
    assert steps["benchmark:optimize"]["command"] == "relai optimize"


def test_benchmark_samples_do_not_duplicate_learning_env_behaviors():
    benchmark_path = PROJECT_ROOT / "benchmarks" / "airline_support_benchmark.csv"
    with benchmark_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    sample_ids = {row["sample_id"] for row in rows}
    sample_text = " ".join(
        value.lower()
        for row in rows
        for value in row.values()
    )

    assert len(rows) == 4
    assert "off-topic-cookie" not in sample_ids
    assert "please let me know if you have any questions" not in sample_text
    assert "chocolate chip cookie" not in sample_text
    assert "standard baggage policy" not in sample_text


def test_reset_track_outputs_deletes_generated_relai_files(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "evaluators").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "optimizer_runs").mkdir()
    (relai_dir / "optimizer-state").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "response-token-smoke-test.py").write_text("", encoding="utf-8")
    (relai_dir / "evaluators" / "response-token.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "response-token-smoke-test-simulation.json").write_text("{}", encoding="utf-8")
    (relai_dir / "optimizer-scope.json").write_text("{}", encoding="utf-8")

    result = reset_track_outputs(project_root=tmp_path, track_id=GLOBAL_EVALUATOR_TRACK_ID)

    assert result["trackId"] == "global-evaluator"
    assert sorted(result["deleted"]) == [
        ".relai/evaluators/response-token.py",
        ".relai/learning-envs/response-token-smoke-test.py",
        ".relai/optimizer-scope.json",
        ".relai/optimizer-state",
        ".relai/optimizer_runs",
        ".relai/runs/response-token-smoke-test-simulation.json",
    ]
    assert (relai_dir / "simulator").exists()
    assert (relai_dir / "learning-env-context.json").exists()
    assert not (relai_dir / "learning-envs" / "response-token-smoke-test.py").exists()
    assert not (relai_dir / "evaluators" / "response-token.py").exists()
    assert not (relai_dir / "runs" / "response-token-smoke-test-simulation.json").exists()
    assert not (relai_dir / "optimizer-scope.json").exists()
    assert not (relai_dir / "optimizer_runs").exists()
    assert not (relai_dir / "optimizer-state").exists()


def test_global_evaluator_track_commands_and_artifacts(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "evaluators").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "response-token-smoke-test.py").write_text("", encoding="utf-8")
    (relai_dir / "evaluators" / "response-token.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "response-token-smoke-test-simulation.json").write_text("{}", encoding="utf-8")

    status = walkthrough_status(project_root=tmp_path, track_id=GLOBAL_EVALUATOR_TRACK_ID)
    steps = {step["id"]: step for step in status["steps"]}

    assert status["selectedTrack"]["kind"] == "global-evaluator"
    assert status["envName"] == "response-token-smoke-test"
    assert steps["global-evaluator:learning-env"]["succeeded"] is True
    assert steps["global-evaluator:evaluator"]["succeeded"] is True
    assert steps["global-evaluator:simulate"]["succeeded"] is True
    assert "relai evaluator create" in steps["global-evaluator:evaluator"]["command"]
    assert "scores 0 when any agent response is above 100 tokens" in steps["global-evaluator:evaluator"]["command"]
    assert "--name response-token" in steps["global-evaluator:evaluator"]["command"]
    assert (
        steps["global-evaluator:simulate"]["command"]
        == "relai simulate --learning-envs response-token-smoke-test "
        "--result-json .relai/runs/response-token-smoke-test-simulation.json"
    )
    assert steps["global-evaluator:optimize"]["command"] == "relai optimize"


def test_env_name_is_shell_safe_slug():
    assert normalize_env_name("Airline Support Policy!") == "airline-support-policy"


def test_prerequisites_status(tmp_path, monkeypatch):
    config_path = tmp_path / "home" / ".relai" / "config.toml"
    project_root = tmp_path / "project"
    project_root.mkdir()
    relai_installed = False

    def fake_which(command: str) -> str | None:
        if command == "relai" and relai_installed:
            return "/usr/local/bin/relai"
        return None

    monkeypatch.setattr("airline_support.walkthrough.shutil.which", fake_which)

    status = prerequisites_status(project_root=project_root, config_path=config_path)
    steps = {step["id"]: step for step in status["steps"]}

    assert [step["id"] for step in status["steps"]] == ["install-cli", "setup", "init"]
    assert status["ready"] is False
    assert steps["install-cli"]["succeeded"] is False
    assert steps["install-cli"]["command"] == "uv tool install relai"
    assert steps["setup"]["succeeded"] is False
    assert steps["setup"]["command"] == "relai setup"
    assert steps["init"]["succeeded"] is False

    relai_installed = True
    config_path.parent.mkdir(parents=True)
    config_path.write_text("", encoding="utf-8")
    (project_root / ".relai" / "simulator").mkdir(parents=True)
    (project_root / ".relai" / "learning-env-context.json").write_text("{}", encoding="utf-8")

    ready_status = prerequisites_status(project_root=project_root, config_path=config_path)
    assert ready_status["ready"] is True
    assert all(step["succeeded"] for step in ready_status["steps"])
