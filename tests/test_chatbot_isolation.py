"""Verifies the AI career assistant's chat history is persisted per student
and never leaks between students, now that it's DB-backed instead of a
session cookie."""


def _register_student(client, email, name):
    client.post("/register/student", data={
        "full_name": name, "email": email, "password": "Passw0rd123",
        "confirm_password": "Passw0rd123", "branch": "CS", "year_of_study": "2",
    })


def test_chat_messages_are_isolated_per_student(app, client, monkeypatch):
    import services.groq_service as groq_service
    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion", lambda *a, **k: "A reply.")

    _register_student(client, "chat_a@test.edu", "Chat A")
    client.post("/ai/career-assistant", data={"message": "Hello from A"})
    client.post("/logout")

    _register_student(client, "chat_b@test.edu", "Chat B")
    client.post("/ai/career-assistant", data={"message": "Hello from B"})

    with app.app_context():
        from database.models import User, ChatMessage

        profile_a = User.query.filter_by(email="chat_a@test.edu").first().student_profile
        profile_b = User.query.filter_by(email="chat_b@test.edu").first().student_profile

        messages_a = ChatMessage.query.filter_by(student_profile_id=profile_a.id).all()
        messages_b = ChatMessage.query.filter_by(student_profile_id=profile_b.id).all()

        assert any(m.content == "Hello from A" for m in messages_a)
        assert not any(m.content == "Hello from A" for m in messages_b)
        assert any(m.content == "Hello from B" for m in messages_b)
        assert not any(m.content == "Hello from B" for m in messages_a)


def test_chat_history_view_only_shows_own_messages(app, client, monkeypatch):
    import services.groq_service as groq_service
    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion", lambda *a, **k: "A reply.")

    _register_student(client, "chat_c@test.edu", "Chat C")
    client.post("/ai/career-assistant", data={"message": "Secret message from C"})
    client.post("/logout")

    _register_student(client, "chat_d@test.edu", "Chat D")
    response = client.get("/ai/career-assistant")
    assert b"Secret message from C" not in response.data


def test_clear_chat_only_deletes_own_messages(app, client, monkeypatch):
    import services.groq_service as groq_service
    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion", lambda *a, **k: "A reply.")

    _register_student(client, "chat_e@test.edu", "Chat E")
    client.post("/ai/career-assistant", data={"message": "From E"})
    client.post("/logout")

    _register_student(client, "chat_f@test.edu", "Chat F")
    client.post("/ai/career-assistant", data={"message": "From F"})
    client.post("/ai/career-assistant/clear")

    with app.app_context():
        from database.models import User, ChatMessage
        profile_e = User.query.filter_by(email="chat_e@test.edu").first().student_profile
        profile_f = User.query.filter_by(email="chat_f@test.edu").first().student_profile

        assert ChatMessage.query.filter_by(student_profile_id=profile_f.id).count() == 0
        assert ChatMessage.query.filter_by(student_profile_id=profile_e.id).count() == 2
