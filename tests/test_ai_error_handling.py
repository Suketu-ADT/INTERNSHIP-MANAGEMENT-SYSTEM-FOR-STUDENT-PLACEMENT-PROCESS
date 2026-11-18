"""Tests that AI failures (timeouts, API errors, malformed JSON) degrade
gracefully instead of 500ing or showing fabricated data. Groq is never
actually called here - groq_service is monkeypatched."""
from datetime import date, timedelta


def _register_student_with_resume(app, client):
    client.post("/register/student", data={
        "full_name": "AI Test Student", "email": "ai_test@test.edu", "password": "Passw0rd123",
        "confirm_password": "Passw0rd123", "branch": "Computer Science", "year_of_study": "3",
    })
    from database.models import db, User, Resume
    with app.app_context():
        user = User.query.filter_by(email="ai_test@test.edu").first()
        profile = user.student_profile
        resume = Resume(
            student_profile_id=profile.id, original_filename="r.pdf", stored_filename="r.pdf",
            file_path="/tmp/r.pdf", file_size=10, parsed_text="Some resume text with Python and React.",
        )
        db.session.add(resume)
        db.session.commit()


def test_resume_analyzer_shows_configured_message_without_key(app, client):
    _register_student_with_resume(app, client)
    response = client.post("/ai/resume-analyzer", follow_redirects=True)
    assert b"not configured" in response.data


def test_resume_analyzer_handles_ai_service_error_gracefully(app, client, monkeypatch):
    _register_student_with_resume(app, client)

    import services.groq_service as groq_service

    def _boom(*args, **kwargs):
        raise groq_service.AIServiceError("simulated timeout")

    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion_json", _boom)

    response = client.post("/ai/resume-analyzer", follow_redirects=True)
    assert response.status_code == 200
    assert b"temporarily unavailable" in response.data


def test_resume_analyzer_handles_malformed_json_from_model(app, client, monkeypatch):
    _register_student_with_resume(app, client)

    import services.groq_service as groq_service
    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    # Simulate the model returning valid JSON that doesn't match our schema at all.
    monkeypatch.setattr(groq_service, "chat_completion_json", lambda *a, **k: {"unexpected": "shape"})

    response = client.post("/ai/resume-analyzer", follow_redirects=True)
    assert response.status_code == 200
    # Must not crash, AND must not save a fabricated score built from an
    # incomplete response (no summary, no score_breakdown here at all).
    assert b"could not be generated" in response.data.lower()
    from database.models import AIAnalysis
    with app.app_context():
        analysis = AIAnalysis.query.filter_by(analysis_type="resume_analysis").first()
        assert analysis is None


def test_match_endpoint_returns_502_on_ai_service_error(app, client, monkeypatch):
    from database.models import db, User, Company, Internship, EligibilityCriteria

    _register_student_with_resume(app, client)
    with app.app_context():
        company_user = User(email="ai_match_co@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="AI Match Co", is_approved=True)
        db.session.add(company)
        db.session.flush()
        internship = Internship(
            company_id=company.id, title="Role", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))
        db.session.commit()
        internship_id = internship.id

    import services.groq_service as groq_service

    def _boom(*args, **kwargs):
        raise groq_service.AIServiceError("simulated failure")

    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion_json", _boom)

    response = client.post(f"/ai/match/{internship_id}")
    assert response.status_code == 502
    assert response.get_json()["error"]


def test_match_endpoint_never_overrides_hard_eligibility_with_ai_score(app, client, monkeypatch):
    """Even if the AI returns a perfect semantic score, a student who fails
    hard eligibility must still show hard_eligible: False."""
    from database.models import db, User, Company, Internship, EligibilityCriteria

    _register_student_with_resume(app, client)
    with app.app_context():
        company_user = User(email="ai_hard_co@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="Hard Co", is_approved=True)
        db.session.add(company)
        db.session.flush()
        internship = Internship(
            company_id=company.id, title="Role", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        # Impossible CGPA requirement - the student will always fail hard eligibility.
        db.session.add(EligibilityCriteria(internship_id=internship.id, min_cgpa=9.9))
        db.session.commit()
        internship_id = internship.id

    import services.groq_service as groq_service
    monkeypatch.setattr(groq_service, "is_configured", lambda: True)
    monkeypatch.setattr(groq_service, "chat_completion_json", lambda *a, **k: {
        "matching_skills": ["Python"], "missing_skills": [],
        "semantic_fit_score": 100, "explanation": "Perfect fit", "suggestions": [],
    })

    response = client.post(f"/ai/match/{internship_id}")
    data = response.get_json()
    assert data["hard_eligible"] is False
