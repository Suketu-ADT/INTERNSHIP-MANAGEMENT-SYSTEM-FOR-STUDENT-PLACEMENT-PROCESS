from datetime import date, timedelta

from services.application_service import (
    can_company_set_status, can_withdraw, can_respond_to_offer, allowed_next_statuses,
)


def _setup_application(app, student_year="2", min_year=None):
    from database.models import (
        db, User, StudentProfile, AcademicDetails, Company, Internship, EligibilityCriteria, Application
    )
    with app.app_context():
        student_user = User(email="wf_student@test.edu", role="student")
        student_user.set_password("Passw0rd123")
        db.session.add(student_user)
        db.session.flush()
        profile = StudentProfile(user_id=student_user.id, full_name="WF Student",
                                  branch="Computer Science", year_of_study=student_year)
        db.session.add(profile)
        db.session.flush()
        db.session.add(AcademicDetails(student_profile_id=profile.id, degree="B.Tech",
                                        institution="Test", cgpa=8.0, percentage_12=80))

        company_user = User(email="wf_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="WF Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship = Internship(
            company_id=company.id, title="WF Internship", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=1000, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=30), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id, min_cgpa=7.0, min_year=min_year))

        application = Application(student_profile_id=profile.id, internship_id=internship.id, status="pending")
        db.session.add(application)
        db.session.commit()
        return application.id, profile.id, internship.id


def test_valid_transition_allowed():
    assert can_company_set_status("pending", "under_review") is True
    assert can_company_set_status("shortlisted", "selected") is True


def test_invalid_transition_rejected():
    assert can_company_set_status("pending", "selected") is False
    assert can_company_set_status("rejected", "shortlisted") is False
    assert can_company_set_status("selected", "pending") is False


def test_terminal_states_have_no_next_statuses():
    assert allowed_next_statuses("selected") == set()
    assert allowed_next_statuses("rejected") == set()
    assert allowed_next_statuses("withdrawn") == set()


def test_withdraw_allowed_only_while_in_play():
    assert can_withdraw("pending") is True
    assert can_withdraw("shortlisted") is True
    assert can_withdraw("selected") is False
    assert can_withdraw("rejected") is False


def test_offer_response_allowed_only_when_selected():
    assert can_respond_to_offer("selected") is True
    assert can_respond_to_offer("pending") is False
    assert can_respond_to_offer("shortlisted") is False


def test_company_cannot_skip_straight_to_selected(app, client):
    app_id, _, _ = _setup_application(app)

    with client.session_transaction():
        pass
    # log in as the company that owns this internship
    client.post("/login", data={"email": "wf_company@test.edu", "password": "Passw0rd123"})

    response = client.post(f"/applications/{app_id}/status", data={"status": "selected"}, follow_redirects=True)
    assert b"Cannot move an application" in response.data

    with app.app_context():
        from database.models import Application
        application = Application.query.get(app_id)
        assert application.status == "pending"


def test_company_can_move_through_valid_sequence(app, client):
    app_id, _, _ = _setup_application(app)
    client.post("/login", data={"email": "wf_company@test.edu", "password": "Passw0rd123"})

    client.post(f"/applications/{app_id}/status", data={"status": "under_review"})
    client.post(f"/applications/{app_id}/status", data={"status": "shortlisted"})
    response = client.post(f"/applications/{app_id}/status", data={"status": "selected"}, follow_redirects=True)
    assert b"Application status updated" in response.data

    with app.app_context():
        from database.models import Application
        application = Application.query.get(app_id)
        assert application.status == "selected"


def test_student_can_accept_offer_only_after_selected(app, client):
    app_id, _, _ = _setup_application(app)
    client.post("/login", data={"email": "wf_company@test.edu", "password": "Passw0rd123"})
    client.post(f"/applications/{app_id}/status", data={"status": "under_review"})
    client.post(f"/applications/{app_id}/status", data={"status": "shortlisted"})
    client.post(f"/applications/{app_id}/status", data={"status": "selected"})
    client.post("/logout")

    client.post("/login", data={"email": "wf_student@test.edu", "password": "Passw0rd123"})
    response = client.post(f"/applications/{app_id}/offer/accept", follow_redirects=True)
    assert b"Offer accepted" in response.data

    with app.app_context():
        from database.models import Application
        application = Application.query.get(app_id)
        assert application.status == "offer_accepted"


def test_min_year_eligibility_blocks_junior_students(app):
    from services.eligibility_service import check_eligibility
    from database.models import StudentProfile, Internship

    app_id, profile_id, internship_id = _setup_application(app, student_year="1", min_year="3")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        eligible, reasons = check_eligibility(profile, internship)
        assert eligible is False
        assert any("Year of study" in r for r in reasons)


def test_min_year_eligibility_passes_senior_students(app):
    from services.eligibility_service import check_eligibility
    from database.models import StudentProfile, Internship

    app_id, profile_id, internship_id = _setup_application(app, student_year="4", min_year="3")
    with app.app_context():
        profile = StudentProfile.query.get(profile_id)
        internship = Internship.query.get(internship_id)
        eligible, reasons = check_eligibility(profile, internship)
        assert eligible is True


def test_withdraw_notifies_company(app, client):
    app_id, profile_id, internship_id = _setup_application(app)
    client.post("/login", data={"email": "wf_student@test.edu", "password": "Passw0rd123"})

    response = client.post(f"/applications/{app_id}/withdraw", follow_redirects=True)
    assert b"Application withdrawn" in response.data

    with app.app_context():
        from database.models import Notification, Application
        application = Application.query.get(app_id)
        company_user = application.internship.company.user
        notes = Notification.query.filter_by(user_id=company_user.id).all()
        assert any("withdrew" in n.message for n in notes)


def test_student_cannot_hit_recruiter_only_status_endpoint(app, client):
    """A student must never be able to drive update_status - only the
    student-specific withdraw/offer endpoints are available to them."""
    app_id, profile_id, internship_id = _setup_application(app)
    client.post("/login", data={"email": "wf_student@test.edu", "password": "Passw0rd123"})

    response = client.post(f"/applications/{app_id}/status", data={"status": "selected"})
    assert response.status_code == 403

    with app.app_context():
        from database.models import Application
        application = Application.query.get(app_id)
        assert application.status == "pending"


def test_every_transition_recorded_in_status_history(app, client):
    app_id, profile_id, internship_id = _setup_application(app)
    client.post("/login", data={"email": "wf_company@test.edu", "password": "Passw0rd123"})
    client.post(f"/applications/{app_id}/status", data={"status": "under_review"})
    client.post(f"/applications/{app_id}/status", data={"status": "shortlisted"})

    with app.app_context():
        from database.models import ApplicationStatusHistory
        # _setup_application() creates the row directly (bypassing the real
        # /apply/ route), so no initial "pending" history entry exists here -
        # only the two transitions made through update_status are asserted.
        statuses = [h.status for h in ApplicationStatusHistory.query.filter_by(
            application_id=app_id).order_by(ApplicationStatusHistory.changed_at).all()]
        assert statuses == ["under_review", "shortlisted"]


def test_apply_route_records_initial_pending_history(app, client):
    """The real apply() route (unlike the test helper above) must record
    the initial 'pending' entry too."""
    from datetime import date, timedelta
    from database.models import (
        db, User, StudentProfile, AcademicDetails, Company, Internship, EligibilityCriteria
    )
    with app.app_context():
        student_user = User(email="apply_hist@test.edu", role="student")
        student_user.set_password("Passw0rd123")
        db.session.add(student_user)
        db.session.flush()
        profile = StudentProfile(user_id=student_user.id, full_name="Apply Hist",
                                  branch="CS", year_of_study="2")
        db.session.add(profile)
        db.session.flush()
        db.session.add(AcademicDetails(student_profile_id=profile.id, degree="B.Tech",
                                        institution="Test", cgpa=8.0, percentage_12=80))

        company_user = User(email="apply_hist_co@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="Apply Hist Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship = Internship(
            company_id=company.id, title="Apply Hist Role", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))
        db.session.commit()
        internship_id = internship.id

    client.post("/login", data={"email": "apply_hist@test.edu", "password": "Passw0rd123"})
    client.post(f"/applications/apply/{internship_id}")

    with app.app_context():
        from database.models import Application, ApplicationStatusHistory
        application = Application.query.filter_by(internship_id=internship_id).first()
        statuses = [h.status for h in ApplicationStatusHistory.query.filter_by(
            application_id=application.id).all()]
        assert statuses == ["pending"]
