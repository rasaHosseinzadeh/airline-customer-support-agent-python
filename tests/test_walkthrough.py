from __future__ import annotations

from airline_support.walkthrough import LOG_TRACK_ID, normalize_env_name, walkthrough_status


def test_prompt_track_commands_and_artifacts(tmp_path):
    relai_dir = tmp_path / ".relai"
    (relai_dir / "simulator").mkdir(parents=True)
    (relai_dir / "learning-envs").mkdir()
    (relai_dir / "runs").mkdir()
    (relai_dir / "learning-env-context.json").write_text("{}", encoding="utf-8")
    (relai_dir / "learning-envs" / "airline-support-policy.py").write_text("", encoding="utf-8")
    (relai_dir / "runs" / "airline-support-policy-simulation.json").write_text("{}", encoding="utf-8")

    status = walkthrough_status(project_root=tmp_path)
    steps = {step["id"]: step for step in status["steps"]}

    assert status["selectedTrack"]["id"] == "intended-behavior"
    assert "init" not in steps
    assert steps["intended-behavior:learning-env"]["succeeded"] is True
    assert steps["intended-behavior:simulate"]["succeeded"] is True
    assert "--prompt" in steps["intended-behavior:learning-env"]["command"]
    assert "--name airline-support-policy" in steps["intended-behavior:learning-env"]["command"]


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


def test_env_name_is_shell_safe_slug():
    assert normalize_env_name("Airline Support Policy!") == "airline-support-policy"
