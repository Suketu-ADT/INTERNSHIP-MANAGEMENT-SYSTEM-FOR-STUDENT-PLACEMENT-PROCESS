import os
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database.models import db, Internship, EligibilityCriteria, Application, Interview, ApplicationStatusHistory
from forms import CompanyProfileForm, InternshipForm, InterviewForm
from services import interview_service
from services.notification_service import notify
from utils.decorators import role_required, company_approved_required
from utils.helpers import allowed_file, unique_filename

company_bp = Blueprint("company", __name__)

PER_PAGE = 20


@company_bp.route("/dashboard")
@login_required
@role_required("company")
def dashboard():
    company = current_user.company
    posts = company.internships

    active_posts = posts.filter(Internship.status == "approved").count()
    total_applicants = Application.query.join(Internship).filter(Internship.company_id == company.id).count()
    shortlisted = Application.query.join(Internship).filter(
        Internship.company_id == company.id, Application.status == "shortlisted").count()
    selected = (
        db.session.query(Application.student_profile_id).join(Internship)
        .filter(Internship.company_id == company.id,
                Application.status.in_(("selected", "offer_accepted")))
        .distinct().count()
    )

    recent_posts = posts.order_by(Internship.posted_at.desc()).limit(5).all()
    recent_applications = (
        Application.query.join(Internship).filter(Internship.company_id == company.id)
        .order_by(Application.applied_at.desc()).limit(5).all()
    )

    return render_template(
        "company/dashboard.html", company=company, active_posts=active_posts,
        total_applicants=total_applicants, shortlisted=shortlisted, selected=selected,
        recent_posts=recent_posts, recent_applications=recent_applications,
    )


@company_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("company")
def profile():
    company = current_user.company
    form = CompanyProfileForm(obj=company)
    if request.method == "GET":
        form.company_name.data = company.company_name
        form.industry.data = company.industry
        form.website.data = company.website
        form.description.data = company.description
        form.contact_person.data = company.contact_person
        form.contact_phone.data = company.contact_phone

    if form.validate_on_submit():
        company.company_name = form.company_name.data.strip()
        company.industry = form.industry.data
        company.website = form.website.data
        company.description = form.description.data
        company.contact_person = form.contact_person.data
        company.contact_phone = form.contact_phone.data

        file = form.logo.data
        if file and allowed_file(file.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            filename = unique_filename(secure_filename(file.filename))
            path = os.path.join(current_app.config["UPLOAD_FOLDER_LOGOS"], filename)
            file.save(path)
            company.logo = filename

        db.session.commit()
        flash("Company profile updated.", "success")
        return redirect(url_for("company.profile"))

    return render_template("company/profile.html", form=form, company=company)


@company_bp.route("/internships")
@login_required
@role_required("company")
def my_internships():
    company = current_user.company
    status_filter = request.args.get("status", "")
    query = company.internships.order_by(Internship.posted_at.desc())
    if status_filter:
        query = query.filter(Internship.status == status_filter)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("company/my_internships.html", posts=pagination.items, pagination=pagination,
                            status_filter=status_filter, today=date.today())


@company_bp.route("/internships/new", methods=["GET", "POST"])
@login_required
@company_approved_required
def new_internship():
    form = InternshipForm()
    if form.validate_on_submit():
        internship = Internship(
            company_id=current_user.company.id, title=form.title.data.strip(),
            description=form.description.data, required_skills=form.required_skills.data,
            domain=form.domain.data.strip(), location=form.location.data.strip(),
            work_mode=form.work_mode.data, stipend=form.stipend.data or 0,
            duration_weeks=form.duration_weeks.data, openings=form.openings.data,
            application_deadline=form.application_deadline.data, status="pending_approval",
        )
        db.session.add(internship)
        db.session.flush()
        db.session.add(EligibilityCriteria(
            internship_id=internship.id, min_cgpa=form.min_cgpa.data or 0,
            min_percentage=form.min_percentage.data or 0,
            eligible_branches=form.eligible_branches.data,
            min_year=form.min_year.data or None,
        ))
        db.session.commit()
        flash("Internship submitted for admin approval.", "success")
        return redirect(url_for("company.my_internships"))
    return render_template("company/internship_form.html", form=form, mode="create")


@company_bp.route("/internships/<int:internship_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("company")
def edit_internship(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    if internship.company_id != current_user.company.id:
        abort(403)

    form = InternshipForm(obj=internship)
    if request.method == "GET":
        if internship.eligibility:
            form.min_cgpa.data = internship.eligibility.min_cgpa
            form.min_percentage.data = internship.eligibility.min_percentage
            form.eligible_branches.data = internship.eligibility.eligible_branches
            form.min_year.data = internship.eligibility.min_year or ""

    if form.validate_on_submit():
        internship.title = form.title.data.strip()
        internship.description = form.description.data
        internship.required_skills = form.required_skills.data
        internship.domain = form.domain.data.strip()
        internship.location = form.location.data.strip()
        internship.work_mode = form.work_mode.data
        internship.stipend = form.stipend.data or 0
        internship.duration_weeks = form.duration_weeks.data
        internship.openings = form.openings.data
        internship.application_deadline = form.application_deadline.data
        internship.status = "pending_approval"  # re-approval required on edit

        if not internship.eligibility:
            internship.eligibility = EligibilityCriteria(internship_id=internship.id)
        internship.eligibility.min_cgpa = form.min_cgpa.data or 0
        internship.eligibility.min_percentage = form.min_percentage.data or 0
        internship.eligibility.eligible_branches = form.eligible_branches.data
        internship.eligibility.min_year = form.min_year.data or None

        db.session.commit()
        flash("Internship updated and resubmitted for approval.", "success")
        return redirect(url_for("company.my_internships"))

    return render_template("company/internship_form.html", form=form, mode="edit", internship=internship)


@company_bp.route("/internships/<int:internship_id>/close", methods=["POST"])
@login_required
@role_required("company")
def close_internship(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    if internship.company_id != current_user.company.id:
        abort(403)
    internship.status = "closed"
    db.session.commit()
    flash("Internship posting closed.", "info")
    return redirect(url_for("company.my_internships"))


@company_bp.route("/internships/<int:internship_id>/applications")
@login_required
@role_required("company")
def internship_applications(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    if internship.company_id != current_user.company.id:
        abort(403)
    status_filter = request.args.get("status", "")
    query = internship.applications.order_by(Application.applied_at.desc())
    if status_filter:
        query = query.filter(Application.status == status_filter)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("company/internship_applications.html", internship=internship,
                            applications=pagination.items, pagination=pagination,
                            status_filter=status_filter)


@company_bp.route("/applications/<int:application_id>")
@login_required
@role_required("company")
def view_application(application_id):
    from routes.application_routes import detail as application_detail
    return application_detail(application_id)


@company_bp.route("/applications/<int:application_id>/interview", methods=["POST"])
@login_required
@role_required("company")
def schedule_interview(application_id):
    application = Application.query.get_or_404(application_id)
    if application.internship.company.user_id != current_user.id:
        abort(403)
    if application.status not in ("shortlisted", "interview_scheduled"):
        flash("Interviews can only be scheduled for shortlisted candidates.", "danger")
        return redirect(url_for("application.detail", application_id=application_id))
    if interview_service.has_active_interview(application):
        flash("This application already has an active scheduled interview. "
              "Reschedule or cancel it before scheduling a new one.", "danger")
        return redirect(url_for("application.detail", application_id=application_id))

    form = InterviewForm()
    if form.validate_on_submit():
        try:
            scheduled_at = datetime.strptime(form.scheduled_at.data, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Invalid date/time format.", "danger")
            return redirect(url_for("application.detail", application_id=application_id))

        ok, error = interview_service.validate_schedule_datetime(scheduled_at)
        if not ok:
            flash(error, "danger")
            return redirect(url_for("application.detail", application_id=application_id))

        interview_service.schedule(
            application, scheduled_at, form.mode.data, form.location_or_link.data,
            form.notes.data, changed_by="company",
        )
        application.status = "interview_scheduled"
        db.session.add(ApplicationStatusHistory(
            application_id=application.id, status="interview_scheduled", changed_by="company",
            notes="Interview scheduled.",
        ))
        db.session.commit()

        notify(application.student_profile.user_id,
               f"Interview scheduled for '{application.internship.title}' on "
               f"{scheduled_at.strftime('%d %b %Y, %I:%M %p')}.",
               category="interview", link=url_for("application.detail", application_id=application.id))
        flash("Interview scheduled.", "success")
    else:
        flash("Could not schedule interview. Check the date/time field.", "danger")
    return redirect(url_for("application.detail", application_id=application_id))


@company_bp.route("/interviews/<int:interview_id>/reschedule", methods=["POST"])
@login_required
@role_required("company")
def reschedule_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    application = interview.application
    if application.internship.company.user_id != current_user.id:
        abort(403)
    if interview.status != "scheduled":
        flash("Only a currently scheduled interview can be rescheduled.", "danger")
        return redirect(url_for("application.detail", application_id=application.id))

    raw_datetime = request.form.get("scheduled_at", "")
    try:
        new_scheduled_at = datetime.strptime(raw_datetime, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("Invalid date/time format.", "danger")
        return redirect(url_for("application.detail", application_id=application.id))

    ok, error = interview_service.validate_schedule_datetime(new_scheduled_at)
    if not ok:
        flash(error, "danger")
        return redirect(url_for("application.detail", application_id=application.id))

    interview_service.reschedule(
        interview, new_scheduled_at, request.form.get("location_or_link"), changed_by="company",
    )
    db.session.commit()

    notify(application.student_profile.user_id,
           f"Your interview for '{application.internship.title}' was rescheduled to "
           f"{interview.scheduled_at.strftime('%d %b %Y, %I:%M %p')}.",
           category="interview", link=url_for("application.detail", application_id=application.id))
    flash("Interview rescheduled.", "success")
    return redirect(url_for("application.detail", application_id=application.id))


@company_bp.route("/interviews/<int:interview_id>/cancel", methods=["POST"])
@login_required
@role_required("company")
def cancel_interview(interview_id):
    interview = Interview.query.get_or_404(interview_id)
    application = interview.application
    if application.internship.company.user_id != current_user.id:
        abort(403)
    if interview.status != "scheduled":
        flash("This interview is not currently active.", "danger")
        return redirect(url_for("application.detail", application_id=application.id))

    cancelled_at = interview.scheduled_at
    interview_service.cancel(interview, changed_by="company")
    db.session.commit()

    notify(application.student_profile.user_id,
           f"Your interview for '{application.internship.title}' on "
           f"{cancelled_at.strftime('%d %b %Y, %I:%M %p')} was cancelled.",
           category="interview", link=url_for("application.detail", application_id=application.id))
    flash("Interview cancelled.", "info")
    return redirect(url_for("application.detail", application_id=application.id))


@company_bp.route("/interviews")
@login_required
@role_required("company")
def interviews():
    company = current_user.company
    upcoming = (
        Interview.query.join(Application).join(Internship)
        .filter(Internship.company_id == company.id, Interview.status == "scheduled")
        .order_by(Interview.scheduled_at.asc()).all()
    )
    return render_template("company/interviews.html", interviews=upcoming)


@company_bp.route("/candidates/<int:student_profile_id>")
@login_required
@role_required("company")
def view_candidate(student_profile_id):
    from database.models import StudentProfile
    student_profile = StudentProfile.query.get_or_404(student_profile_id)
    # only viewable if the student applied to one of this company's internships
    applications_to_this_company = Application.query.join(Internship).filter(
        Application.student_profile_id == student_profile_id,
        Internship.company_id == current_user.company.id,
    ).order_by(Application.applied_at.desc()).all()
    if not applications_to_this_company:
        abort(403)

    # Only ever surface a resume this company actually received, not the
    # student's current/most-recent resume if that's a different, unrelated
    # upload used for other applications.
    submitted_resume = next((a.resume for a in applications_to_this_company if a.resume), None)

    return render_template("company/candidate_profile.html", profile=student_profile,
                            submitted_resume=submitted_resume)
