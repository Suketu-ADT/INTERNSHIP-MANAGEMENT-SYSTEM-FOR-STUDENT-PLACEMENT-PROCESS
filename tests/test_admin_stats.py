from datetime import date, timedelta


def test_placement_percentage_counts_distinct_students_not_applications(app, client):
    """A student selected for two internships must only count once toward
    the placement percentage, not twice."""
    from database.models import (
        db, User, StudentProfile, Company, Internship, EligibilityCriteria, Application
    )

    with app.app_context():
        student_user = User(email="double_select@test.edu", role="student")
        student_user.set_password("Passw0rd123")
        db.session.add(student_user)
        db.session.flush()
        profile = StudentProfile(user_id=student_user.id, full_name="Double Select",
                                  branch="CS", year_of_study="4")
        db.session.add(profile)
        db.session.flush()

        company_user = User(email="double_select_co@test.edu", role="company")
        company_user.set_password("Passw0rd123")
        db.session.add(company_user)
        db.session.flush()
        company = Company(user_id=company_user.id, company_name="DS Co", is_approved=True)
        db.session.add(company)
        db.session.flush()

        internship_ids = []
        for i in range(2):
            internship = Internship(
                company_id=company.id, title=f"Role {i}", description="desc", domain="Software",
                location="Remote", work_mode="remote", stipend=0, duration_weeks=4, openings=1,
                application_deadline=date.today() + timedelta(days=10), status="approved",
            )
            db.session.add(internship)
            db.session.flush()
            db.session.add(EligibilityCriteria(internship_id=internship.id))
            db.session.add(Application(student_profile_id=profile.id, internship_id=internship.id,
                                        status="selected"))
            internship_ids.append(internship.id)
        db.session.commit()

    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})
    response = client.get("/admin/dashboard")
    html = response.data.decode()

    # total_students is 1 (only this student has a profile), and exactly
    # one student is selected (across two applications), so placement % = 100.0, not 200.
    assert "100.0%" in html
    assert "200.0%" not in html
