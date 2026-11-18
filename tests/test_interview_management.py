from datetime import date, datetime, timedelta


def _setup_shortlisted_application(app):
    from database.models import (
        db, User, StudentProfile, AcademicDetails, Company, Internship, EligibilityCriteria, Application,
        ApplicationStatusHistory,
    )
    with app.app_context():
        student_user = User(email="iv_student@test.edu", role="student")
        student_user.set_password("Passw0rd123")
        db.session.add(student_user)
        db.session.flush()
        profile = StudentProfile(user_id=student_user.id, full_name="Interview Student",
                                  branch="CS", year_of_study="3")
        db.session.add(profile)
        db.session.flush()
        db.session.add(AcademicDetails(student_profile_id=profile.id, degree="B.Tech",
                                        institution="Test", cgpa=8.0, percentage_12=80))

        company_user = User(email="iv_company@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="IV Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship = Internship(
            company_id=company.id, title="IV Internship", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=30), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))

        application = Application(student_profile_id=profile.id, internship_id=internship.id,
                                   status="shortlisted")
        db.session.add(application)
        db.session.flush()
        db.session.add(ApplicationStatusHistory(application_id=application.id, status="shortlisted",
                                                  changed_by="company"))
        db.session.commit()
        return application.id


def _future_dt(days=5):
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _past_dt(days=5):
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def test_cannot_schedule_interview_in_the_past(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})

    response = client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _past_dt(), "mode": "online", "location_or_link": "", "notes": "",
    }, follow_redirects=True)
    assert b"must be in the future" in response.data

    with app.app_context():
        from database.models import Interview
        assert Interview.query.filter_by(application_id=app_id).count() == 0


def test_can_schedule_interview_in_the_future(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})

    response = client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(), "mode": "online", "location_or_link": "https://x.test", "notes": "",
    }, follow_redirects=True)
    assert b"Interview scheduled" in response.data

    with app.app_context():
        from database.models import Interview, Application
        assert Interview.query.filter_by(application_id=app_id, status="scheduled").count() == 1
        assert Application.query.get(app_id).status == "interview_scheduled"


def test_cannot_schedule_duplicate_active_interview(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})

    client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(3), "mode": "online", "location_or_link": "", "notes": "",
    })
    response = client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(7), "mode": "online", "location_or_link": "", "notes": "",
    }, follow_redirects=True)
    assert b"already has an active scheduled interview" in response.data

    with app.app_context():
        from database.models import Interview
        assert Interview.query.filter_by(application_id=app_id, status="scheduled").count() == 1


def test_reschedule_rejects_past_date_and_records_history(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})
    client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(3), "mode": "online", "location_or_link": "", "notes": "",
    })

    with app.app_context():
        from database.models import Interview
        interview_id = Interview.query.filter_by(application_id=app_id).first().id

    # Past date rejected
    response = client.post(f"/company/interviews/{interview_id}/reschedule", data={
        "scheduled_at": _past_dt(), "location_or_link": "",
    }, follow_redirects=True)
    assert b"must be in the future" in response.data

    # Valid reschedule accepted and recorded
    response = client.post(f"/company/interviews/{interview_id}/reschedule", data={
        "scheduled_at": _future_dt(10), "location_or_link": "https://new-link.test",
    }, follow_redirects=True)
    assert b"Interview rescheduled" in response.data

    with app.app_context():
        from database.models import InterviewHistory
        actions = [h.action for h in InterviewHistory.query.filter_by(interview_id=interview_id)
                   .order_by(InterviewHistory.changed_at).all()]
        assert actions == ["scheduled", "rescheduled"]


def test_cancel_records_history_notifies_student_and_reverts_application_status(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})
    client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(3), "mode": "online", "location_or_link": "", "notes": "",
    })

    with app.app_context():
        from database.models import Interview, Application
        interview_id = Interview.query.filter_by(application_id=app_id).first().id
        assert Application.query.get(app_id).status == "interview_scheduled"

    response = client.post(f"/company/interviews/{interview_id}/cancel", follow_redirects=True)
    assert b"Interview cancelled" in response.data

    with app.app_context():
        from database.models import Interview, InterviewHistory, Application, Notification
        interview = Interview.query.get(interview_id)
        assert interview.status == "cancelled"

        actions = [h.action for h in InterviewHistory.query.filter_by(interview_id=interview_id)
                   .order_by(InterviewHistory.changed_at).all()]
        assert actions == ["scheduled", "cancelled"]

        # Application reverts to shortlisted since no other active interview exists.
        application = Application.query.get(app_id)
        assert application.status == "shortlisted"

        student_user = application.student_profile.user
        notes = Notification.query.filter_by(user_id=student_user.id).all()
        assert any("cancelled" in n.message for n in notes)


def test_cannot_cancel_already_cancelled_interview_twice(app, client):
    app_id = _setup_shortlisted_application(app)
    client.post("/login", data={"email": "iv_company@test.edu", "password": "Passw0rd123"})
    client.post(f"/company/applications/{app_id}/interview", data={
        "scheduled_at": _future_dt(3), "mode": "online", "location_or_link": "", "notes": "",
    })
    with app.app_context():
        from database.models import Interview
        interview_id = Interview.query.filter_by(application_id=app_id).first().id

    client.post(f"/company/interviews/{interview_id}/cancel")
    response = client.post(f"/company/interviews/{interview_id}/cancel", follow_redirects=True)
    assert b"not currently active" in response.data
