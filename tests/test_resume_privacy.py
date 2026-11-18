from datetime import date, timedelta


def _register_student(client, email, name="Resume Student"):
    client.post("/register/student", data={
        "full_name": name, "email": email, "password": "Passw0rd123",
        "confirm_password": "Passw0rd123", "branch": "Computer Science", "year_of_study": "3",
    })


def _register_company(client, email, name="Resume Co"):
    client.post("/register/company", data={
        "company_name": name, "email": email, "password": "Passw0rd123",
        "confirm_password": "Passw0rd123", "industry": "Tech", "website": "", "contact_person": "X",
    })


def _make_resume(app, profile_email):
    from database.models import db, User, Resume
    with app.app_context():
        user = User.query.filter_by(email=profile_email).first()
        profile = user.student_profile
        resume = Resume(
            student_profile_id=profile.id, original_filename="resume.pdf",
            stored_filename="stored_resume.pdf", file_path="/tmp/does-not-matter.pdf",
            file_size=100, parsed_text="Some resume text",
        )
        db.session.add(resume)
        db.session.commit()
        return resume.id


def test_static_resume_url_is_not_served(app, client):
    """Resumes must never be reachable through Flask's static file route."""
    _register_student(client, "static_test@test.edu")
    _make_resume(app, "static_test@test.edu")
    # the old (insecure) path pattern must 404 - static/ no longer holds resumes
    response = client.get("/static/uploads/resumes/stored_resume.pdf")
    assert response.status_code == 404


def test_owner_can_access_own_resume_endpoint(app, client):
    _register_student(client, "owner_test@test.edu")
    resume_id = _make_resume(app, "owner_test@test.edu")
    response = client.get(f"/applications/resume/{resume_id}")
    # Werkzeug will 404 trying to actually read the fake file, but it must
    # NOT be a 403 - permission was granted to the owner.
    assert response.status_code != 403


def test_unrelated_student_cannot_access_someone_elses_resume(app, client):
    _register_student(client, "owner2@test.edu")
    resume_id = _make_resume(app, "owner2@test.edu")
    client.post("/logout")

    _register_student(client, "stranger@test.edu")
    response = client.get(f"/applications/resume/{resume_id}")
    assert response.status_code == 403


def test_unrelated_company_cannot_access_resume_without_application(app, client):
    _register_student(client, "owner3@test.edu")
    resume_id = _make_resume(app, "owner3@test.edu")
    client.post("/logout")

    _register_company(client, "unrelated_co@test.edu")
    response = client.get(f"/applications/resume/{resume_id}")
    assert response.status_code == 403


def test_company_with_application_can_access_resume(app, client):
    from database.models import (
        db, User, Company, Internship, EligibilityCriteria, Application
    )

    _register_student(client, "applicant@test.edu")
    resume_id = _make_resume(app, "applicant@test.edu")
    client.post("/logout")

    _register_company(client, "hiring_co@test.edu")
    client.post("/logout")

    with app.app_context():
        company = Company.query.join(User).filter(User.email == "hiring_co@test.edu").first()
        company.is_approved = True
        student_user = User.query.filter_by(email="applicant@test.edu").first()
        profile = student_user.student_profile

        internship = Internship(
            company_id=company.id, title="Test Role", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship.id))
        db.session.add(Application(student_profile_id=profile.id, internship_id=internship.id,
                                    resume_id=resume_id, status="pending"))
        db.session.commit()

    client.post("/login", data={"email": "hiring_co@test.edu", "password": "Passw0rd123"})
    response = client.get(f"/applications/resume/{resume_id}")
    assert response.status_code != 403


def test_company_cannot_access_unrelated_historical_resume(app, client):
    """A company that received an application tied to Resume A must not be
    able to view Resume B from the same student just because the student
    later used Resume B for a DIFFERENT application elsewhere - exact
    resume_id-to-application-at-that-company is what matters, not just
    'this company received some application from this student'."""
    from database.models import (
        db, User, Company, Internship, EligibilityCriteria, Application
    )

    _register_student(client, "multi_resume@test.edu")
    old_resume_id = _make_resume(app, "multi_resume@test.edu")
    client.post("/logout")

    _register_company(client, "co_a@test.edu", "Company A")
    client.post("/logout")
    _register_company(client, "co_b@test.edu", "Company B")
    client.post("/logout")

    with app.app_context():
        student_user = User.query.filter_by(email="multi_resume@test.edu").first()
        profile = student_user.student_profile

        # A newer resume, used only for an application to Company B.
        from database.models import Resume
        new_resume = Resume(
            student_profile_id=profile.id, original_filename="resume_v2.pdf",
            stored_filename="resume_v2.pdf", file_path="/tmp/resume_v2.pdf",
            file_size=100, parsed_text="Updated resume text",
        )
        db.session.add(new_resume)
        db.session.flush()
        new_resume_id = new_resume.id

        company_a = Company.query.join(User).filter(User.email == "co_a@test.edu").first()
        company_a.is_approved = True
        company_b = Company.query.join(User).filter(User.email == "co_b@test.edu").first()
        company_b.is_approved = True

        internship_a = Internship(
            company_id=company_a.id, title="Role A", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        internship_b = Internship(
            company_id=company_b.id, title="Role B", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
            application_deadline=date.today() + timedelta(days=10), status="approved",
        )
        db.session.add_all([internship_a, internship_b])
        db.session.flush()
        db.session.add(EligibilityCriteria(internship_id=internship_a.id))
        db.session.add(EligibilityCriteria(internship_id=internship_b.id))
        # Company A received the OLD resume; Company B received the NEW one.
        db.session.add(Application(student_profile_id=profile.id, internship_id=internship_a.id,
                                    resume_id=old_resume_id, status="pending"))
        db.session.add(Application(student_profile_id=profile.id, internship_id=internship_b.id,
                                    resume_id=new_resume_id, status="pending"))
        db.session.commit()

    client.post("/login", data={"email": "co_a@test.edu", "password": "Passw0rd123"})
    # Company A may view the resume actually submitted to them...
    response = client.get(f"/applications/resume/{old_resume_id}")
    assert response.status_code != 403
    # ...but NOT the unrelated resume the same student used for Company B.
    response = client.get(f"/applications/resume/{new_resume_id}")
    assert response.status_code == 403
