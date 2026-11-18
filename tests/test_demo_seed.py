"""Tests for database/seed_demo.py and the admin demo-data management
routes. ENABLE_DEMO_SEED is False in TestConfig (see conftest.py), so
these tests call the seeder explicitly rather than relying on startup."""


def test_seed_demo_data_creates_companies_and_internships(app):
    from database.models import Company, Internship
    from database.seed_demo import seed_demo_data

    with app.app_context():
        seed_demo_data()
        companies = Company.query.filter_by(is_demo=True).all()
        internships = Internship.query.filter_by(is_demo=True).all()
        assert len(companies) == 8
        assert len(internships) >= 12
        # Every demo company is pre-approved and every demo internship is
        # pre-approved, so the platform doesn't look empty on a fresh install.
        assert all(c.is_approved for c in companies)
        assert all(i.status == "approved" for i in internships)


def test_seed_demo_data_is_idempotent(app):
    """Calling it twice must not create duplicate companies/internships/
    applications/accounts."""
    from database.models import Company, Internship, Application, User
    from database.seed_demo import seed_demo_data

    with app.app_context():
        seed_demo_data()
        first_company_count = Company.query.filter_by(is_demo=True).count()
        first_internship_count = Internship.query.filter_by(is_demo=True).count()
        first_application_count = Application.query.count()
        first_user_count = User.query.count()

        seed_demo_data()
        assert Company.query.filter_by(is_demo=True).count() == first_company_count
        assert Internship.query.filter_by(is_demo=True).count() == first_internship_count
        assert Application.query.count() == first_application_count
        assert User.query.count() == first_user_count


def test_seed_demo_data_creates_a_populated_demo_student(app):
    """The demo student shouldn't just be an empty profile - it should have
    a resume and a spread of in-progress applications, so logging in shows
    a genuinely populated dashboard rather than another onboarding screen."""
    from database.models import StudentProfile, User, Application, Interview
    from database.seed_demo import seed_demo_data, DEMO_STUDENT_EMAIL

    with app.app_context():
        seed_demo_data()
        user = User.query.filter_by(email=DEMO_STUDENT_EMAIL).first()
        assert user is not None
        assert user.role == "student"
        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        assert profile is not None

        resume = profile.resumes.first()
        assert resume is not None
        assert resume.parsed_text  # has real extractable text, not blank
        import os
        assert os.path.exists(resume.file_path)

        applications = Application.query.filter_by(student_profile_id=profile.id).all()
        assert len(applications) == 6
        statuses = {a.status for a in applications}
        assert statuses == {"pending", "under_review", "shortlisted",
                             "interview_scheduled", "selected", "rejected"}
        # Every application has a history that starts at "pending" and ends
        # at its current status - a real lifecycle, not a single raw status.
        for a in applications:
            history = a.status_history.all()  # relationship is pre-ordered by changed_at
            assert history[0].status == "pending"
            assert history[-1].status == a.status

        interview_app = next(a for a in applications if a.status == "interview_scheduled")
        assert Interview.query.filter_by(application_id=interview_app.id).count() == 1


def test_seed_demo_data_creates_a_demo_admin_account(app, client):
    from database.models import User
    from database.seed_demo import seed_demo_data, DEMO_ADMIN_EMAIL, DEMO_PASSWORD

    with app.app_context():
        seed_demo_data()
        user = User.query.filter_by(email=DEMO_ADMIN_EMAIL).first()
        assert user is not None
        assert user.role == "admin"

    response = client.post("/login", data={"email": DEMO_ADMIN_EMAIL, "password": DEMO_PASSWORD},
                            follow_redirects=True)
    assert response.status_code == 200
    assert b"Placement Office Dashboard" in response.data


def test_seed_demo_data_never_touches_real_companies(app):
    from database.models import db, User, Company
    from database.seed_demo import seed_demo_data

    with app.app_context():
        real_user = User(email="real_company@test.edu", role="company")
        real_user.set_password("Passw0rd123")
        db.session.add(real_user)
        db.session.flush()
        real_company = Company(user_id=real_user.id, company_name="Real Co", is_approved=False)
        db.session.add(real_company)
        db.session.commit()
        real_company_id = real_company.id

        seed_demo_data()

        real_company = Company.query.get(real_company_id)
        assert real_company is not None
        assert real_company.is_demo is False
        assert real_company.is_approved is False  # untouched


def test_remove_demo_data_deletes_only_demo_records(app):
    import os
    from database.models import db, User, Company, Internship, Application
    from database.seed_demo import seed_demo_data, remove_demo_data, DEMO_STUDENT_EMAIL, DEMO_ADMIN_EMAIL

    with app.app_context():
        real_user = User(email="real_company2@test.edu", role="company")
        real_user.set_password("Passw0rd123")
        db.session.add(real_user)
        db.session.flush()
        db.session.add(Company(user_id=real_user.id, company_name="Real Co 2", is_approved=True))
        db.session.commit()

        seed_demo_data()
        assert Company.query.filter_by(is_demo=True).count() == 8
        demo_student = User.query.filter_by(email=DEMO_STUDENT_EMAIL).first()
        resume_path = demo_student.student_profile.resumes.first().file_path
        assert os.path.exists(resume_path)

        remove_demo_data()

        assert Company.query.filter_by(is_demo=True).count() == 0
        assert Internship.query.filter_by(is_demo=True).count() == 0
        assert Company.query.filter_by(company_name="Real Co 2").count() == 1
        assert User.query.filter_by(email=DEMO_STUDENT_EMAIL).first() is None
        assert User.query.filter_by(email=DEMO_ADMIN_EMAIL).first() is None
        assert Application.query.count() == 0
        assert not os.path.exists(resume_path)


def test_admin_demo_data_page_requires_admin(app, client):
    from database.models import db, User, StudentProfile

    with app.app_context():
        user = User(email="not_admin@test.edu", role="student")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        db.session.add(StudentProfile(user_id=user.id, full_name="Not Admin", branch="CS", year_of_study="2"))
        db.session.commit()

    client.post("/login", data={"email": "not_admin@test.edu", "password": "Passw0rd123"})
    response = client.get("/admin/demo-data")
    assert response.status_code == 403


def test_admin_can_reseed_and_remove_demo_data(app, client):
    from database.models import Company

    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})

    response = client.post("/admin/demo-data/reseed", follow_redirects=True)
    assert b"Demo Data" in response.data
    with app.app_context():
        assert Company.query.filter_by(is_demo=True).count() == 8

    response = client.post("/admin/demo-data/remove", follow_redirects=True)
    assert b"removed" in response.data.lower()
    with app.app_context():
        assert Company.query.filter_by(is_demo=True).count() == 0


def test_cannot_delete_a_non_demo_company_via_demo_route(app, client):
    from database.models import db, User, Company

    with app.app_context():
        real_user = User(email="real_company3@test.edu", role="company")
        real_user.set_password("Passw0rd123")
        db.session.add(real_user)
        db.session.flush()
        real_company = Company(user_id=real_user.id, company_name="Real Co 3", is_approved=True)
        db.session.add(real_company)
        db.session.commit()
        real_company_id = real_company.id

    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})
    response = client.post(f"/admin/demo-data/companies/{real_company_id}/delete", follow_redirects=True)
    assert b"Only demo companies" in response.data

    with app.app_context():
        assert Company.query.get(real_company_id) is not None
