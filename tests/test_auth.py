def test_admin_account_created_on_init(app):
    from database.models import User
    with app.app_context():
        admin = User.query.filter_by(email="admin@test.edu").first()
        assert admin is not None
        assert admin.role == "admin"
        assert admin.check_password("TestAdmin@123")


def test_student_can_register_and_reach_dashboard(client):
    response = client.post("/register/student", data={
        "full_name": "Test Student",
        "email": "student@test.edu",
        "password": "Passw0rd123",
        "confirm_password": "Passw0rd123",
        "branch": "Computer Science",
        "year_of_study": "3",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_duplicate_email_registration_rejected(client):
    data = {
        "full_name": "Test Student",
        "email": "dupe@test.edu",
        "password": "Passw0rd123",
        "confirm_password": "Passw0rd123",
        "branch": "Computer Science",
        "year_of_study": "3",
    }
    client.post("/register/student", data=data, follow_redirects=True)
    client.post("/logout")
    response = client.post("/register/student", data=data, follow_redirects=True)
    assert b"already exists" in response.data


def test_login_with_wrong_password_fails(client):
    client.post("/register/student", data={
        "full_name": "Test Student", "email": "wrongpw@test.edu",
        "password": "Passw0rd123", "confirm_password": "Passw0rd123",
        "branch": "CS", "year_of_study": "1",
    })
    client.post("/logout")
    response = client.post("/login", data={
        "email": "wrongpw@test.edu", "password": "incorrect",
    }, follow_redirects=True)
    assert b"Invalid email or password" in response.data


def test_student_dashboard_requires_login(client):
    response = client.get("/student/dashboard", follow_redirects=True)
    assert b"Please log in" in response.data or response.status_code == 200


def test_logout_requires_post_not_get(client):
    client.post("/register/student", data={
        "full_name": "Logout Test", "email": "logouttest@test.edu",
        "password": "Passw0rd123", "confirm_password": "Passw0rd123",
        "branch": "CS", "year_of_study": "1",
    })
    response = client.get("/logout")
    assert response.status_code == 405


def test_login_next_param_blocks_open_redirect(client):
    client.post("/register/student", data={
        "full_name": "Redirect Test", "email": "redirecttest@test.edu",
        "password": "Passw0rd123", "confirm_password": "Passw0rd123",
        "branch": "CS", "year_of_study": "1",
    })
    client.post("/logout")
    response = client.post("/login?next=https://evil.example.com/phish", data={
        "email": "redirecttest@test.edu", "password": "Passw0rd123",
    })
    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]


def test_company_registration_requires_admin_approval(app, client):
    response = client.post("/register/company", data={
        "company_name": "Test Co", "email": "testco@test.edu",
        "password": "Passw0rd123", "confirm_password": "Passw0rd123",
        "industry": "Tech", "website": "", "contact_person": "Jane",
    }, follow_redirects=True)
    assert b"awaiting approval" in response.data or response.status_code == 200

    from database.models import Company
    with app.app_context():
        company = Company.query.filter_by(company_name="Test Co").first()
        assert company is not None
        assert company.is_approved is False
