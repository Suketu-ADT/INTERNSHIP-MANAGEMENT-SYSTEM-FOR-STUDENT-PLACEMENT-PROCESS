from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from sqlalchemy import func

from database.models import (
    db, User, StudentProfile, Company, Internship, Application, Interview
)
from services.notification_service import notify
from utils.decorators import role_required

admin_bp = Blueprint("admin", __name__)

PER_PAGE = 20


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    total_students = StudentProfile.query.count()
    total_companies = Company.query.filter_by(is_approved=True).count()
    pending_companies = Company.query.filter_by(is_approved=False).count()
    active_internships = Internship.query.filter_by(status="approved").count()
    pending_internships = Internship.query.filter_by(status="pending_approval").count()
    total_applications = Application.query.count()
    # Count distinct STUDENTS with at least one selected application, not
    # applications - a student selected for two internships must count once.
    selected_students = (
        db.session.query(Application.student_profile_id)
        .filter(Application.status.in_(("selected", "offer_accepted")))
        .distinct().count()
    )

    placement_percentage = round((selected_students / total_students) * 100, 1) if total_students else 0

    # Accurate to the card's own heading ("Pending Company/Internship
    # Approvals") - the most recently submitted ones actually awaiting a
    # decision, not just the most recently created regardless of status.
    pending_company_list = Company.query.filter_by(is_approved=False).order_by(
        Company.created_at.desc()).limit(5).all()
    pending_internship_list = Internship.query.filter_by(status="pending_approval").order_by(
        Internship.posted_at.desc()).limit(5).all()
    recent_applications = Application.query.order_by(Application.applied_at.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html", total_students=total_students, total_companies=total_companies,
        pending_companies=pending_companies, active_internships=active_internships,
        pending_internships=pending_internships, total_applications=total_applications,
        selected_students=selected_students, placement_percentage=placement_percentage,
        pending_company_list=pending_company_list, pending_internship_list=pending_internship_list,
        recent_applications=recent_applications,
    )


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------
@admin_bp.route("/students")
@login_required
@role_required("admin")
def students():
    search = request.args.get("q", "").strip()
    branch = request.args.get("branch", "").strip()
    query = StudentProfile.query.join(User)
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(StudentProfile.full_name.ilike(like), User.email.ilike(like)))
    if branch:
        query = query.filter(StudentProfile.branch == branch)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(StudentProfile.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    branches = [b[0] for b in db.session.query(StudentProfile.branch).distinct() if b[0]]
    return render_template("admin/students.html", profiles=pagination.items, pagination=pagination,
                            branches=branches, filters={"q": search, "branch": branch})


@admin_bp.route("/students/<int:profile_id>")
@login_required
@role_required("admin")
def view_student(profile_id):
    profile = StudentProfile.query.get_or_404(profile_id)
    return render_template("admin/student_detail.html", profile=profile)


@admin_bp.route("/students/<int:profile_id>/toggle-active", methods=["POST"])
@login_required
@role_required("admin")
def toggle_student_active(profile_id):
    profile = StudentProfile.query.get_or_404(profile_id)
    profile.user.is_active_account = not profile.user.is_active_account
    db.session.commit()
    flash("Student account updated.", "success")
    return redirect(url_for("admin.view_student", profile_id=profile_id))


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
@admin_bp.route("/companies")
@login_required
@role_required("admin")
def companies():
    status_filter = request.args.get("status", "")
    query = Company.query
    if status_filter == "pending":
        query = query.filter_by(is_approved=False)
    elif status_filter == "approved":
        query = query.filter_by(is_approved=True)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Company.created_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template("admin/companies.html", companies=pagination.items, pagination=pagination,
                            status_filter=status_filter)


@admin_bp.route("/companies/<int:company_id>")
@login_required
@role_required("admin")
def view_company(company_id):
    company = Company.query.get_or_404(company_id)
    return render_template("admin/company_detail.html", company=company)


@admin_bp.route("/companies/<int:company_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_company(company_id):
    company = Company.query.get_or_404(company_id)
    company.is_approved = True
    company.approved_at = datetime.utcnow()
    db.session.commit()
    notify(company.user_id, "Your company account has been approved. You can now post internships.",
           category="approval", link=url_for("company.dashboard"))
    flash(f"{company.company_name} approved.", "success")
    return redirect(url_for("admin.companies"))


@admin_bp.route("/companies/<int:company_id>/reject", methods=["POST"])
@login_required
@role_required("admin")
def reject_company(company_id):
    company = Company.query.get_or_404(company_id)
    company.is_approved = False
    company.user.is_active_account = False
    db.session.commit()
    notify(company.user_id, "Your company registration has been rejected by the placement office.",
           category="approval")
    flash(f"{company.company_name} rejected.", "info")
    return redirect(url_for("admin.companies"))


# ---------------------------------------------------------------------------
# Internships
# ---------------------------------------------------------------------------
@admin_bp.route("/internships")
@login_required
@role_required("admin")
def internships():
    status_filter = request.args.get("status", "")
    query = Internship.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Internship.posted_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template("admin/internships.html", posts=pagination.items, pagination=pagination,
                            status_filter=status_filter)


@admin_bp.route("/internships/<int:internship_id>")
@login_required
@role_required("admin")
def view_internship(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    return render_template("admin/internship_detail.html", internship=internship)


@admin_bp.route("/internships/<int:internship_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_internship(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    internship.status = "approved"
    db.session.commit()
    notify(internship.company.user_id, f"Your internship posting '{internship.title}' was approved.",
           category="approval", link=url_for("company.my_internships"))
    flash("Internship approved.", "success")
    return redirect(url_for("admin.internships"))


@admin_bp.route("/internships/<int:internship_id>/reject", methods=["POST"])
@login_required
@role_required("admin")
def reject_internship(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    internship.status = "rejected"
    db.session.commit()
    notify(internship.company.user_id, f"Your internship posting '{internship.title}' was rejected.",
           category="approval", link=url_for("company.my_internships"))
    flash("Internship rejected.", "info")
    return redirect(url_for("admin.internships"))


# ---------------------------------------------------------------------------
# Applications / Interviews / Placements
# ---------------------------------------------------------------------------
@admin_bp.route("/applications")
@login_required
@role_required("admin")
def applications():
    status_filter = request.args.get("status", "")
    query = Application.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Application.applied_at.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template("admin/applications.html", applications=pagination.items,
                            pagination=pagination, status_filter=status_filter)


@admin_bp.route("/interviews")
@login_required
@role_required("admin")
def interviews():
    page = request.args.get("page", 1, type=int)
    pagination = Interview.query.order_by(Interview.scheduled_at.asc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    return render_template("admin/interviews.html", interviews=pagination.items, pagination=pagination)


@admin_bp.route("/placements")
@login_required
@role_required("admin")
def placements():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Application.query.filter(Application.status.in_(("selected", "offer_accepted")))
        .order_by(Application.updated_at.desc())
        .paginate(page=page, per_page=PER_PAGE, error_out=False)
    )
    return render_template("admin/placements.html", applications=pagination.items, pagination=pagination)


# ---------------------------------------------------------------------------
# Reports & Analytics
# ---------------------------------------------------------------------------
@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    return render_template("admin/reports.html")


@admin_bp.route("/reports/export")
@login_required
@role_required("admin")
def export_report():
    import pandas as pd
    import io
    from flask import send_file

    rows = []
    for app_ in Application.query.all():
        rows.append({
            "Student": app_.student_profile.full_name,
            "Branch": app_.student_profile.branch,
            "Internship": app_.internship.title,
            "Company": app_.internship.company.company_name,
            "Status": app_.status,
            "Applied On": app_.applied_at.strftime("%Y-%m-%d") if app_.applied_at else "",
        })
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return send_file(buffer, mimetype="text/csv", as_attachment=True,
                      download_name="placement_report.csv")


@admin_bp.route("/api/charts/applications-by-status")
@login_required
@role_required("admin")
def chart_applications_by_status():
    results = db.session.query(Application.status, func.count(Application.id)).group_by(Application.status).all()
    return jsonify({"labels": [r[0] for r in results], "data": [r[1] for r in results]})


@admin_bp.route("/api/charts/monthly-trends")
@login_required
@role_required("admin")
def chart_monthly_trends():
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    results = (
        db.session.query(func.strftime("%Y-%m", Application.applied_at), func.count(Application.id))
        .filter(Application.applied_at >= six_months_ago)
        .group_by(func.strftime("%Y-%m", Application.applied_at))
        .order_by(func.strftime("%Y-%m", Application.applied_at))
        .all()
    )
    return jsonify({"labels": [r[0] for r in results], "data": [r[1] for r in results]})


@admin_bp.route("/api/charts/internships-by-domain")
@login_required
@role_required("admin")
def chart_internships_by_domain():
    results = (
        db.session.query(Internship.domain, func.count(Internship.id))
        .filter(Internship.status == "approved").group_by(Internship.domain).all()
    )
    return jsonify({"labels": [r[0] or "Other" for r in results], "data": [r[1] for r in results]})


@admin_bp.route("/api/charts/company-participation")
@login_required
@role_required("admin")
def chart_company_participation():
    results = (
        db.session.query(Company.company_name, func.count(Internship.id))
        .join(Internship, Internship.company_id == Company.id)
        .group_by(Company.company_name)
        .order_by(func.count(Internship.id).desc())
        .limit(10).all()
    )
    return jsonify({"labels": [r[0] for r in results], "data": [r[1] for r in results]})


@admin_bp.route("/api/charts/students-selected")
@login_required
@role_required("admin")
def chart_students_selected():
    # Distinct students per branch, not applications - a student selected
    # for two internships in the same branch must only count once.
    results = (
        db.session.query(StudentProfile.branch, func.count(func.distinct(StudentProfile.id)))
        .join(Application, Application.student_profile_id == StudentProfile.id)
        .filter(Application.status.in_(("selected", "offer_accepted")))
        .group_by(StudentProfile.branch).all()
    )
    return jsonify({"labels": [r[0] or "Unknown" for r in results], "data": [r[1] for r in results]})


# ---------------------------------------------------------------------------
# Notifications / activity
# ---------------------------------------------------------------------------
@admin_bp.route("/activity")
@login_required
@role_required("admin")
def activity():
    from database.models import ApplicationStatusHistory
    events = ApplicationStatusHistory.query.order_by(ApplicationStatusHistory.changed_at.desc()).limit(100).all()
    return render_template("admin/activity.html", events=events)


# ---------------------------------------------------------------------------
# Demo data management
# ---------------------------------------------------------------------------
@admin_bp.route("/demo-data")
@login_required
@role_required("admin")
def demo_data():
    demo_companies = Company.query.filter_by(is_demo=True).order_by(Company.company_name).all()
    demo_internship_count = Internship.query.filter_by(is_demo=True).count()
    from database.models import User
    demo_student = User.query.filter_by(email="demo.student@example.com", role="student").first()
    return render_template(
        "admin/demo_data.html", demo_companies=demo_companies,
        demo_internship_count=demo_internship_count, demo_student=demo_student,
    )


@admin_bp.route("/demo-data/remove", methods=["POST"])
@login_required
@role_required("admin")
def remove_demo_data():
    from database.seed_demo import remove_demo_data as _remove_demo_data
    _remove_demo_data()
    flash("Demo companies, internships and the demo student account have been removed.", "info")
    return redirect(url_for("admin.demo_data"))


@admin_bp.route("/demo-data/reseed", methods=["POST"])
@login_required
@role_required("admin")
def reseed_demo_data():
    from database.seed_demo import seed_demo_data
    seed_demo_data()
    flash("Demo data seeded.", "success")
    return redirect(url_for("admin.demo_data"))


@admin_bp.route("/demo-data/companies/<int:company_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_demo_company(company_id):
    company = Company.query.get_or_404(company_id)
    if not company.is_demo:
        flash("Only demo companies can be deleted from here.", "danger")
        return redirect(url_for("admin.demo_data"))
    db.session.delete(company.user)
    db.session.commit()
    flash(f"{company.company_name} (demo) removed.", "info")
    return redirect(url_for("admin.demo_data"))
