import os
from flask import Flask, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from config import Config, DEFAULT_INSECURE_SECRET_KEY
from database.models import db, User
from database.db_init import init_db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["SECRET_KEY"] == DEFAULT_INSECURE_SECRET_KEY:
        if not app.config.get("DEBUG") and not app.config.get("TESTING"):
            raise RuntimeError(
                "Refusing to start: SECRET_KEY is still the default insecure "
                "value and FLASK_DEBUG=False. Set a real SECRET_KEY in .env."
            )
        print("[WARNING] Using the default insecure SECRET_KEY. Set a real "
              "random SECRET_KEY in .env before deploying or exposing this app.")

    db.init_app(app)
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from routes.auth_routes import auth_bp
    from routes.student_routes import student_bp
    from routes.company_routes import company_bp
    from routes.admin_routes import admin_bp
    from routes.internship_routes import internship_bp
    from routes.application_routes import application_bp
    from routes.ai_routes import ai_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(company_bp, url_prefix="/company")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(internship_bp, url_prefix="/internships")
    app.register_blueprint(application_bp, url_prefix="/applications")
    app.register_blueprint(ai_bp, url_prefix="/ai")

    from utils.helpers import time_ago
    app.jinja_env.filters["time_ago"] = time_ago

    @app.context_processor
    def inject_notification_count():
        from flask_login import current_user
        from services.notification_service import unread_count
        if current_user.is_authenticated:
            return {"unread_notifications": unread_count(current_user.id)}
        return {"unread_notifications": 0}

    @app.context_processor
    def inject_current_year():
        from datetime import date
        return {"current_year": date.today().year}

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.errorhandler(413)
    def file_too_large(e):
        from flask import flash, redirect, request
        max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        flash(f"The uploaded file is too large. Maximum size is {max_mb}MB.", "danger")
        return redirect(request.referrer or url_for("auth.index")), 413

    os.makedirs(app.config["UPLOAD_FOLDER_RESUMES"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER_LOGOS"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "database"), exist_ok=True)

    init_db(app)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], host="127.0.0.1", port=5000)
