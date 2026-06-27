from __future__ import annotations

import json

from fastapi.testclient import TestClient

from airline_support.main import app
from airline_support.main import cors_origins


def test_cors_origins_supports_launcher_config(monkeypatch):
    monkeypatch.setenv(
        "AIRLINE_SUPPORT_CORS_ORIGINS",
        "http://localhost:3001, http://127.0.0.1:3001",
    )

    assert cors_origins() == ["http://localhost:3001", "http://127.0.0.1:3001"]


def test_stream_chat_logs_messages(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRLINE_SUPPORT_LOG_DIR", str(tmp_path))

    async def fake_stream_agent_response(messages):
        assert messages[-1].content == "What is the baggage policy?"
        yield "Standard tickets include "
        yield "one checked bag."

    monkeypatch.setattr("airline_support.main.stream_agent_response", fake_stream_agent_response)

    client = TestClient(app)
    response = client.post(
        "/api/chat/stream",
        json={"message": "What is the baggage policy?"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: token" in body
    assert "one checked bag" in body
    assert "event: done" in body

    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    done_payload = json.loads(data_lines[-1])
    session_id = done_payload["sessionId"]
    log_text = (tmp_path / f"{session_id}.jsonl").read_text(encoding="utf-8")
    assert "What is the baggage policy?" in log_text
    assert "Standard tickets include one checked bag." in log_text
