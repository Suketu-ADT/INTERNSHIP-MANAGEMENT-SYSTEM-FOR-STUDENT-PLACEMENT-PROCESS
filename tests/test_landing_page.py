"""Tests for the redesigned public landing page (templates/index.html)."""
from datetime import date, timedelta


def _approved_student_company_internship(app):
    from database.models import (
        db, User, StudentProfile, Company, Internship, EligibilityCriteria
    )
    with app.app_context():
        student_user = User(email="land_student@test.edu", role="student")
        student_user.set_password("Passw0rd123")
        db.session.add(student_user)
        db.session.flush()
        db.session.add(StudentProfile(user_id=student_user.id, full_name="Land Student",
                                       branch="CS", year_of_study="2"))

        company_user = User(email="land_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="Landing Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship = Internship(
            company_id=company.id, title="Landing Page Intern", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=5000, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=30), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))
        db.session.commit()


def test_landing_page_loads_for_guest(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Your Career Starts With the Right Opportunity." in response.data
    assert b"Explore Internships" in response.data
    assert b"Get Started" in response.data


def test_landing_page_shows_real_stats_not_fabricated(app, client):
    _approved_student_company_internship(app)
    response = client.get("/")
    html = response.data.decode()
    assert "Registered Students" in html
    assert "Registered Companies" in html
    assert "Active Internships" in html
    assert "Students Placed" in html
    # The one approved company/internship we just created must actually show up.
    assert "Landing Co" in html
    assert "Landing Page Intern" in html


def test_landing_page_navigation_links_work(client):
    response = client.get("/")
    html = response.data.decode()
    assert 'href="/login"' in html
    assert 'href="/register/student"' in html
    assert 'href="/register/company"' in html


def test_authenticated_user_is_redirected_away_from_landing_page(app, client):
    from database.models import db, User, StudentProfile
    with app.app_context():
        user = User(email="logged_in@test.edu", role="student")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        db.session.add(StudentProfile(user_id=user.id, full_name="Logged In", branch="CS", year_of_study="2"))
        db.session.commit()

    client.post("/login", data={"email": "logged_in@test.edu", "password": "Passw0rd123"})
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/student/dashboard" in response.headers["Location"]


def test_pending_company_is_not_shown_as_featured(app, client):
    from database.models import db, User, Company
    with app.app_context():
        user = User(email="pending_co@test.edu", role="company")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        db.session.add(Company(user_id=user.id, company_name="Unapproved Co", is_approved=False))
        db.session.commit()

    response = client.get("/")
    assert b"Unapproved Co" not in response.data
