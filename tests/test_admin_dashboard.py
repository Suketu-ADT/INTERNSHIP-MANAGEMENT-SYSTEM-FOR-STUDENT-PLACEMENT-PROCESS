"""Tests for the admin dashboard's pending-approval panels: they must show
only items actually awaiting a decision (not just "recently created"), and
the inline Approve buttons on the dashboard must work exactly like the ones
on the full Companies/Internships pages."""
from datetime import date, timedelta


def _make_pending_company(app, email="pending_dash_co@test.edu", name="Pending Dash Co"):
    from database.models import db, User, Company
    with app.app_context():
        user = User(email=email, role="company")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        company = Company(user_id=user.id, company_name=name, is_approved=False)
        db.session.add(company)
        db.session.commit()
        return company.id


def _make_approved_company_with_pending_internship(app):
    from database.models import db, User, Company, Internship
    with app.app_context():
        user = User(email="approved_dash_co@test.edu", role="company")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        company = Company(user_id=user.id, company_name="Approved Dash Co", is_approved=True)
        db.session.add(company)
        db.session.flush()
        internship = Internship(
            company_id=company.id, title="Pending Dash Role", description="desc", domain="Software",
            location="Remote", work_mode="remote", stipend=0, duration_weeks=8, openings=1,
            application_deadline=date.today() + timedelta(days=20), status="pending_approval",
        )
        db.session.add(internship)
        db.session.commit()
        return internship.id


def test_dashboard_pending_company_panel_excludes_already_approved_companies(app, client):
    from database.models import db, User, Company
    with app.app_context():
        user = User(email="already_approved_co@test.edu", role="company")
        user.set_password("Passw0rd123")
        db.session.add(user)
        db.session.flush()
        db.session.add(Company(user_id=user.id, company_name="Already Approved Co", is_approved=True))
        db.session.commit()

    _make_pending_company(app)
    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})
    response = client.get("/admin/dashboard")
    html = response.data.decode()

    assert "Pending Dash Co" in html
    assert "Already Approved Co" not in html


def test_dashboard_can_approve_a_company_inline(app, client):
    from database.models import Company
    company_id = _make_pending_company(app)
    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})

    response = client.post(f"/admin/companies/{company_id}/approve", follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert Company.query.get(company_id).is_approved is True


def test_dashboard_pending_internship_panel_shows_only_pending_ones(app, client):
    _make_approved_company_with_pending_internship(app)
    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})
    response = client.get("/admin/dashboard")
    assert b"Pending Dash Role" in response.data
    assert b"Pending Internship Approvals" in response.data


def test_dashboard_pending_approvals_stat_links_to_companies_page(client):
    client.post("/login", data={"email": "admin@test.edu", "password": "TestAdmin@123"})
    response = client.get("/admin/dashboard")
    assert b'href="/admin/companies?status=pending"' in response.data
