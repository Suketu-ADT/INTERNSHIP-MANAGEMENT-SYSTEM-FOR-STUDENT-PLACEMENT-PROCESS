"""Tests for internship discovery improvements: the three-state eligibility
indicator (eligible / missing_skills / not_eligible) and browse-page sorting.
Hard eligibility (CGPA/branch/year) must stay exactly as check_eligibility()
already decided it - eligibility_status() only adds a softer skills signal
on top, never changes the hard verdict."""
from datetime import date, timedelta


def _make_student(app, cgpa=8.0, branch="Computer Science", skills=None):
    from database.models import db, User, StudentProfile, AcademicDetails, StudentSkill
    with app.app_context():
        user = User(email="disc_student@test.edu", role="student")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        profile = StudentProfile(user_id=user.id, full_name="Disc Student", branch=branch, year_of_study="3")
        db.session.add(profile)
        db.session.flush()
        db.session.add(AcademicDetails(student_profile_id=profile.id, degree="B.Tech",
                                        institution="Test", cgpa=cgpa, percentage_12=80))
        for skill in (skills or []):
            db.session.add(StudentSkill(student_profile_id=profile.id, skill_name=skill))
        db.session.commit()
        return profile.id


def _make_internship(app, required_skills="", min_cgpa=7.0, eligible_branches="Computer Science",
                      days_until_deadline=30):
    from database.models import db, User, Company, Internship, EligibilityCriteria
    with app.app_context():
        company_user = User(email="disc_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="Disc Co", is_approved=True)
        db.session.add(company)
        db.session.flush()
        internship = Internship(
            company_id=company.id, title="Disc Internship", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=1000, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=days_until_deadline), status="approved",
            required_skills=required_skills,
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(
            internship_id=internship.id, min_cgpa=min_cgpa, eligible_branches=eligible_branches,
        ))
        db.session.commit()
        return internship.id


def test_eligibility_status_not_eligible_when_hard_criteria_fails(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import eligibility_status

    profile_id = _make_student(app, cgpa=5.0)  # below min_cgpa
    internship_id = _make_internship(app, required_skills="Python")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        assert eligibility_status(profile, internship) == "not_eligible"


def test_eligibility_status_eligible_when_no_required_skills(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import eligibility_status

    profile_id = _make_student(app, cgpa=8.5)
    internship_id = _make_internship(app, required_skills="")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        assert eligibility_status(profile, internship) == "eligible"


def test_eligibility_status_missing_skills_when_hard_eligible_but_low_overlap(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import eligibility_status

    profile_id = _make_student(app, cgpa=8.5, skills=["Python"])
    internship_id = _make_internship(app, required_skills="Python, React, SQL, Docker")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        # Hard-eligible (CGPA/branch fine) but only 1 of 4 required skills -> missing_skills.
        assert eligibility_status(profile, internship) == "missing_skills"


def test_eligibility_status_eligible_with_most_skills_present(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import eligibility_status

    profile_id = _make_student(app, cgpa=8.5, skills=["Python", "React", "SQL"])
    internship_id = _make_internship(app, required_skills="Python, React, SQL, Docker")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        # 3 of 4 required skills (75%) >= 50% threshold -> eligible.
        assert eligibility_status(profile, internship) == "eligible"


def test_ai_never_overrides_hard_eligibility():
    """Sanity check that eligibility_status() and check_eligibility() live
    in services/eligibility_service.py and never import matching_service's
    AI-calling functions for the hard verdict - only the pure skill-overlap
    helper, which is plain Python."""
    import inspect
    from services import eligibility_service

    source = inspect.getsource(eligibility_service)
    assert "groq_service" not in source
    assert "chat_completion" not in source


def test_browse_sort_by_deadline_orders_soonest_first(app, client):
    from database.models import db, Internship, User, EligibilityCriteria
    _make_internship(app, days_until_deadline=30)
    with app.app_context():
        company_user = User.query.filter_by(email="disc_company@test.edu").first()
        company = company_user.company
        soon = Internship(
            company_id=company.id, title="Soon Deadline Intern", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=500, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=2), status="approved",
        )
        db.session.add(soon)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=soon.id))
        db.session.commit()

    _make_student(app, cgpa=8.5)
    client.post("/login", data={"email": "disc_student@test.edu", "password": "Passw0rd123"})

    response = client.get("/internships/browse?sort=deadline")
    html = response.data.decode()
    assert html.index("Soon Deadline Intern") < html.index("Disc Internship")


def test_browse_sort_defaults_to_newest_and_rejects_unknown_value(app, client):
    _make_internship(app)
    _make_student(app, cgpa=8.5)
    client.post("/login", data={"email": "disc_student@test.edu", "password": "Passw0rd123"})

    response = client.get("/internships/browse?sort=not-a-real-option")
    assert response.status_code == 200  # falls back to 'newest', doesn't error
