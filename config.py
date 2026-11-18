import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


DEFAULT_INSECURE_SECRET_KEY = "dev-insecure-key-change-me"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_INSECURE_SECRET_KEY)
    DEBUG = os.environ.get("FLASK_DEBUG", "True") == "True"

    db_url = os.environ.get("DATABASE_URL", "sqlite:///database/internship.db")
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        rel_path = db_url.replace("sqlite:///", "", 1)
        db_url = "sqlite:///" + os.path.join(BASE_DIR, rel_path).replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Resumes contain PII and must NEVER be reachable through Flask's public
    # static file serving - they live outside static/ and are only served
    # through the authenticated download route in application_routes.py.
    UPLOAD_FOLDER_RESUMES = os.path.join(BASE_DIR, "uploads", "resumes")
    UPLOAD_FOLDER_LOGOS = os.path.join(BASE_DIR, "static", "uploads", "logos")
    ALLOWED_RESUME_EXTENSIONS = {"pdf", "docx"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", 5)) * 1024 * 1024

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@college.edu")
    # No hardcoded fallback: an empty value tells db_init.py to generate
    # a random password on first run instead of shipping a guessable one.
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    # Seeds clearly-labelled demo companies/internships (database/seed_demo.py)
    # on startup so the app isn't empty for a fresh dev/evaluation setup.
    # Idempotent (skips if demo data already exists) and safe to leave on in
    # development; set to False for a real deployment with real data.
    ENABLE_DEMO_SEED = os.environ.get("ENABLE_DEMO_SEED", "True") == "True"

    WTF_CSRF_ENABLED = True
