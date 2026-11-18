from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from database.models import db, User, StudentProfile, Company, Internship, Application, Notification
from forms import LoginForm, StudentRegisterForm, CompanyRegisterForm
from services.notification_service import mark_all_read

auth_bp = Blueprint("auth", __name__)


def _redirect_for_role(role):
    if role == "student":
        return redirect(url_for("student.dashboard"))
    if role == "company":
        return redirect(url_for("company.dashboard"))
    return redirect(url_for("admin.dashboard"))


def _safe_next_url(candidate):
    """Only allow redirecting to a same-site relative path, never an
    absolute URL or protocol-relative (//host) one, to prevent open
    redirects via the login ?next= parameter."""
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return None
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None
    return candidate


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user.role)

    # All real counts straight from the database - never hardcoded or
    # fabricated. A fresh/demo install will show small, honest numbers.
    stats = {
        "students": StudentProfile.query.count(),
        "companies": Company.query.filter_by(is_approved=True).count(),
        "internships": Internship.query.filter_by(status="approved").count(),
        "placements": (
            db.session.query(Application.student_profile_id)
            .filter(Application.status.in_(("selected", "offer_accepted")))
            .distinct().count()
        ),
    }

    featured_companies = (
        Company.query.filter_by(is_approved=True)
        .join(Internship, Internship.company_id == Company.id)
        .filter(Internship.status == "approved")
        .distinct().order_by(Company.created_at.desc()).limit(8).all()
    )

    featured_internships = (
        Internship.query.filter(
            Internship.status == "approved",
            db.or_(Internship.application_deadline.is_(None), Internship.application_deadline >= date.today()),
        )
        .order_by(Internship.posted_at.desc()).limit(6).all()
    )

    return render_template(
        "index.html", stats=stats, featured_companies=featured_companies,
        featured_internships=featured_internships,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user.role)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            if not user.is_active_account:
                flash("Your account has been deactivated. Contact the placement office.", "danger")
                return redirect(url_for("auth.login"))
            login_user(user)
            flash(f"Welcome back, {user.display_name()}!", "success")
            next_url = _safe_next_url(request.args.get("next"))
            return redirect(next_url) if next_url else _redirect_for_role(user.role)
        flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user.role)

    form = StudentRegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return render_template("register_student.html", form=form)

        user = User(email=email, role="student")
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        profile = StudentProfile(
            user_id=user.id, full_name=form.full_name.data.strip(),
            branch=form.branch.data.strip(), year_of_study=form.year_of_study.data,
        )
        db.session.add(profile)
        db.session.commit()

        login_user(user)
        flash("Account created successfully. Complete your profile to get started.", "success")
        return redirect(url_for("student.dashboard"))
    return render_template("register_student.html", form=form)


@auth_bp.route("/register/company", methods=["GET", "POST"])
def register_company():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user.role)

    form = CompanyRegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return render_template("register_company.html", form=form)

        user = User(email=email, role="company")
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        company = Company(
            user_id=user.id, company_name=form.company_name.data.strip(),
            industry=form.industry.data, website=form.website.data,
            contact_person=form.contact_person.data, is_approved=False,
        )
        db.session.add(company)
        db.session.commit()

        login_user(user)
        flash("Account created. Your company must be approved by the placement office "
              "before you can post internships.", "info")
        return redirect(url_for("company.dashboard"))
    return render_template("register_company.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/notifications")
@login_required
def notifications():
    notes = current_user.notifications.order_by(Notification.created_at.desc()).limit(50).all()
    mark_all_read(current_user.id)
    return render_template("shared/notifications.html", notifications=notes)
