import tempfile

import pytest

from app import create_app
from config import Config
from database.models import db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    GROQ_API_KEY = ""
    SECRET_KEY = "test-secret-key"
    ADMIN_EMAIL = "admin@test.edu"
    ADMIN_PASSWORD = "TestAdmin@123"
    # Tests build their own exact fixtures and assert on exact counts - the
    # demo seeder (database/seed_demo.py) must never run here.
    ENABLE_DEMO_SEED = False


@pytest.fixture
def app():
    upload_dir = tempfile.mkdtemp()
    TestConfig.UPLOAD_FOLDER_RESUMES = upload_dir
    TestConfig.UPLOAD_FOLDER_LOGOS = upload_dir

    flask_app = create_app(TestConfig)
    flask_app.config.update(TESTING=True)

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
