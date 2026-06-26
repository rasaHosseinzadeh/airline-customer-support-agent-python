from __future__ import annotations

from airline_support.sessions import append_message, create_session, list_sessions, read_messages


def test_session_messages_are_logged(monkeypatch, tmp_path):
    monkeypatch.setenv("AIRLINE_SUPPORT_LOG_DIR", str(tmp_path))

    session = create_session()
    append_message(session.id, "user", "Can I change my seat for SKY123?")
    append_message(session.id, "assistant", "I can help after verifying the booking.")

    messages = read_messages(session.id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == "Can I change my seat for SKY123?"

    sessions = list_sessions()
    assert sessions[0].id == session.id
    assert sessions[0].message_count == 2
    assert "change my seat" in sessions[0].preview
