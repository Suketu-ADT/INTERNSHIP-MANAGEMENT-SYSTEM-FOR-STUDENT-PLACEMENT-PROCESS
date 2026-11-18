from datetime import date, timedelta


def _make_student_and_internship(app, cgpa=8.0, branch="Computer Science",
                                   min_cgpa=7.0, eligible_branches="Computer Science"):
    from database.models import (
        db, User, StudentProfile, AcademicDetails, Company, Internship, EligibilityCriteria
    )
    with app.app_context():
        user = User(email="elig_student@test.edu", role="student")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()

        profile = StudentProfile(user_id=user.id, full_name="Elig Student", branch=branch, year_of_study="3")
        db.session.add(profile)
        db.session.flush()

        db.session.add(AcademicDetails(student_profile_id=profile.id, degree="B.Tech",
                                        institution="Test Institute", cgpa=cgpa, percentage_12=80))

        company_user = User(email="elig_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()

        company = Company(user_id=company_user.id, company_name="Elig Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship = Internship(
            company_id=company.id, title="Test Internship", description="desc",
            domain="Software", location="Remote", work_mode="remote", stipend=1000,
            duration_weeks=8, openings=1, application_deadline=date.today() + timedelta(days=30),
            status="approved",
        )
        db.session.add(internship)
        db.session.flush()

        db.session.add(EligibilityCriteria(
            internship_id=internship.id, min_cgpa=min_cgpa, eligible_branches=eligible_branches,
        ))
        db.session.commit()

        return profile.id, internship.id


def test_eligible_student_passes_check(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import check_eligibility

    profile_id, internship_id = _make_student_and_internship(app, cgpa=8.5)
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        eligible, reasons = check_eligibility(profile, internship)
        assert eligible is True
        assert reasons == []


def test_low_cgpa_student_fails_check(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import check_eligibility

    profile_id, internship_id = _make_student_and_internship(app, cgpa=5.0)
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        eligible, reasons = check_eligibility(profile, internship)
        assert eligible is False
        assert any("CGPA" in r for r in reasons)


def test_wrong_branch_student_fails_check(app):
    from database.models import StudentProfile, Internship
    from services.eligibility_service import check_eligibility

    profile_id, internship_id = _make_student_and_internship(app, branch="Mechanical")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        eligible, reasons = check_eligibility(profile, internship)
        assert eligible is False
        assert any("Branch" in r for r in reasons)


def test_duplicate_application_blocked(app):
    from database.models import db, StudentProfile, Internship, Application
    from services.eligibility_service import can_apply

    profile_id, internship_id = _make_student_and_internship(app)
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)

        allowed, reasons = can_apply(profile, internship)
        assert allowed is True

        db.session.add(Application(student_profile_id=profile.id, internship_id=internship.id, status="pending"))
        db.session.commit()

        allowed_again, reasons_again = can_apply(profile, internship)
        assert allowed_again is False
        assert any("already applied" in r for r in reasons_again)


def test_closed_internship_blocks_application(app):
    from database.models import StudentProfile, Internship, db
    from services.eligibility_service import can_apply

    profile_id, internship_id = _make_student_and_internship(app)
    with app.app_context():
        internship = Internship.query.get(internship_id)
        internship.status = "closed"
        db.session.commit()

        profile = StudentProfile.query.get(profile_id)
        allowed, reasons = can_apply(profile, internship)
        assert allowed is False
