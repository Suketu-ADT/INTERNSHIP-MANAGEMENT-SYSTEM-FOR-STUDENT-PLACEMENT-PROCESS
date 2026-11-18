"""Tests for the redesigned student dashboard: student-specific stats,
profile-completion checklist, onboarding state, and that recommended
internships/featured companies are never fabricated."""
from datetime import date, timedelta


def _register_student(client, email="dash_student@test.edu", name="Dash Student"):
    return client.post("/register/student", data={
        "full_name": name, "email": email, "password": "Passw0rd123",
        "confirm_password": "Passw0rd123", "branch": "Computer Science", "year_of_study": "2",
    }, follow_redirects=True)


def _add_approved_company_and_internship(app, title="Dash Internship"):
    from database.models import db, User, Company, Internship, EligibilityCriteria
    with app.app_context():
        company_user = User(email="dash_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="Dash Co", is_approved=True)
        db.session.add(company)
        db.session.flush()
        internship = Internship(
            company_id=company.id, title=title, description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=1000, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=30), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))
        db.session.commit()
        return internship.id


def test_new_student_sees_onboarding_checklist_not_empty_dashboard(app, client):
    _register_student(client)
    response = client.get("/student/dashboard")
    html = response.data.decode()
    assert "Get started" in html
    assert "Add your academic details" in html
    assert "Add at least one skill" in html
    assert "Upload your resume" in html


def test_profile_completion_checklist_shrinks_as_fields_are_filled(app, client):
    _register_student(client)

    response = client.get("/student/dashboard")
    assert b"Add your academic details" in response.data

    client.post("/student/academic", data={
        "degree": "B.Tech", "institution": "Test Institute", "cgpa": "8.0",
        "percentage_10": "85", "percentage_12": "85", "graduation_year": "2026",
    })

    response = client.get("/student/dashboard")
    assert b"Add your academic details" not in response.data
    assert b"Add at least one skill" in response.data


def test_dashboard_stats_are_specific_to_the_logged_in_student(app, client):
    """A second student's applications must never appear in this student's
    stats or recent activity."""
    internship_id = _add_approved_company_and_internship(app)

    _register_student(client, email="dash_student_a@test.edu", name="Student A")
    client.post(f"/applications/apply/{internship_id}")
    client.post("/logout")

    _register_student(client, email="dash_student_b@test.edu", name="Student B")
    response = client.get("/student/dashboard")
    html = response.data.decode()

    # Student B applied to nothing - their own stats must read zero, not
    # pick up student A's application.
    assert "Total Applications" in html
    assert "You haven't applied to any internships yet." in html


def test_recommended_internships_only_includes_real_approved_postings(app, client):
    _add_approved_company_and_internship(app, title="Visible Intern Role")
    _register_student(client)

    response = client.get("/student/dashboard")
    html = response.data.decode()
    assert "Visible Intern Role" in html
    assert "Dash Co" in html


def test_featured_companies_excludes_companies_with_no_approved_internships(app, client):
    from database.models import db, User, Company
    with app.app_context():
        user = User(email="no_postings_co@test.edu", role="company")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        db.session.add(Company(user_id=user.id, company_name="No Postings Co", is_approved=True))
        db.session.commit()

    _register_student(client)
    response = client.get("/student/dashboard")
    assert b"No Postings Co" not in response.data
