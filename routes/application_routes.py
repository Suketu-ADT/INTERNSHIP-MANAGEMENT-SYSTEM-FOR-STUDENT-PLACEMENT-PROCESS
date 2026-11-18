import os

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user

from database.models import db, Application, ApplicationStatusHistory, Internship, Resume
from forms import ApplicationStatusForm, InterviewForm
from services.application_service import (
    STATUS_LABELS, allowed_next_statuses, can_company_set_status, can_withdraw, can_respond_to_offer,
)
from services.eligibility_service import can_apply
from services.notification_service import notify
from services.resume_service import can_view_resume
from utils.decorators import role_required

application_bp = Blueprint("application", __name__)

PER_PAGE = 20


@application_bp.route("/apply/<int:internship_id>", methods=["POST"])
@login_required
@role_required("student")
def apply(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    profile = current_user.student_profile

    allowed, reasons = can_apply(profile, internship)
    if not allowed:
        flash("Could not submit application: " + "; ".join(reasons), "danger")
        return redirect(url_for("internship.detail", internship_id=internship_id))

    resume = profile.active_resume()
    application = Application(
        student_profile_id=profile.id, internship_id=internship.id,
        resume_id=resume.id if resume else None, status="pending",
    )
    db.session.add(application)
    db.session.flush()
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status="pending", changed_by="student",
        notes="Application submitted.",
    ))
    db.session.commit()

    notify(internship.company.user_id,
           f"New application for '{internship.title}' from {profile.full_name}.",
           category="application", link=url_for("company.view_application", application_id=application.id))

    flash("Application submitted successfully!", "success")
    return redirect(url_for("application.mine"))


@application_bp.route("/mine")
@login_required
@role_required("student")
def mine():
    status_filter = request.args.get("status", "")
    profile = current_user.student_profile
    query = profile.applications.order_by(Application.applied_at.desc())
    if status_filter:
        query = query.filter(Application.status == status_filter)
    page = request.args.get("page", 1, type=int)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("student/my_applications.html", applications=pagination.items,
                            pagination=pagination, status_filter=status_filter, status_labels=STATUS_LABELS)


@application_bp.route("/<int:application_id>")
@login_required
def detail(application_id):
    application = Application.query.get_or_404(application_id)
    if current_user.role == "student":
        if application.student_profile.user_id != current_user.id:
            abort(403)
        template = "student/application_detail.html"
    elif current_user.role == "company":
        if application.internship.company.user_id != current_user.id:
            abort(403)
        template = "company/application_detail.html"
    else:
        template = "admin/application_detail.html"

    history = application.status_history.order_by(ApplicationStatusHistory.changed_at.asc()).all()

    next_statuses = allowed_next_statuses(application.status)
    status_form = ApplicationStatusForm()
    status_form.status.choices = [(s, STATUS_LABELS[s]) for s in STATUS_LABELS if s in next_statuses]
    interview_form = InterviewForm()

    return render_template(template, application=application, history=history,
                            status_labels=STATUS_LABELS, status_form=status_form,
                            interview_form=interview_form, has_next_statuses=bool(next_statuses),
                            can_withdraw_now=can_withdraw(application.status),
                            can_respond_offer=can_respond_to_offer(application.status))


@application_bp.route("/<int:application_id>/withdraw", methods=["POST"])
@login_required
@role_required("student")
def withdraw(application_id):
    application = Application.query.get_or_404(application_id)
    if application.student_profile.user_id != current_user.id:
        abort(403)
    if not can_withdraw(application.status):
        flash("This application can no longer be withdrawn.", "warning")
        return redirect(url_for("application.detail", application_id=application_id))

    application.status = "withdrawn"
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status="withdrawn", changed_by="student",
        notes="Withdrawn by student.",
    ))
    db.session.commit()

    notify(application.internship.company.user_id,
           f"{application.student_profile.full_name} withdrew their application for "
           f"'{application.internship.title}'.",
           category="application", link=url_for("application.detail", application_id=application.id))

    flash("Application withdrawn.", "info")
    return redirect(url_for("application.mine"))


@application_bp.route("/<int:application_id>/status", methods=["POST"])
@login_required
@role_required("company", "admin")
def update_status(application_id):
    application = Application.query.get_or_404(application_id)
    if current_user.role == "company" and application.internship.company.user_id != current_user.id:
        abort(403)

    form = ApplicationStatusForm()
    form.status.choices = [(s, l) for s, l in STATUS_LABELS.items()]  # validate against the full set first
    if form.validate_on_submit():
        if not can_company_set_status(application.status, form.status.data):
            flash(f"Cannot move an application from "
                  f"'{STATUS_LABELS.get(application.status, application.status)}' to "
                  f"'{STATUS_LABELS.get(form.status.data, form.status.data)}'.", "danger")
            return redirect(url_for("application.detail", application_id=application_id))

        application.status = form.status.data
        db.session.add(ApplicationStatusHistory(
            application_id=application.id, status=form.status.data,
            changed_by=current_user.role, notes=form.notes.data,
        ))
        db.session.commit()

        student_user_id = application.student_profile.user_id
        label = STATUS_LABELS.get(form.status.data, form.status.data)
        notify(student_user_id,
               f"Your application for '{application.internship.title}' is now: {label}",
               category="application", link=url_for("application.detail", application_id=application.id))
        flash("Application status updated.", "success")
    else:
        flash("Could not update status.", "danger")
    return redirect(url_for("application.detail", application_id=application_id))


@application_bp.route("/<int:application_id>/offer/accept", methods=["POST"])
@login_required
@role_required("student")
def accept_offer(application_id):
    application = Application.query.get_or_404(application_id)
    if application.student_profile.user_id != current_user.id:
        abort(403)
    if not can_respond_to_offer(application.status):
        flash("There is no pending offer to respond to.", "warning")
        return redirect(url_for("application.detail", application_id=application_id))

    application.status = "offer_accepted"
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status="offer_accepted", changed_by="student",
        notes="Offer accepted by student.",
    ))
    db.session.commit()
    notify(application.internship.company.user_id,
           f"{application.student_profile.full_name} accepted the offer for '{application.internship.title}'.",
           category="application", link=url_for("application.detail", application_id=application.id))
    flash("Offer accepted. Congratulations!", "success")
    return redirect(url_for("application.detail", application_id=application_id))


@application_bp.route("/<int:application_id>/offer/decline", methods=["POST"])
@login_required
@role_required("student")
def decline_offer(application_id):
    application = Application.query.get_or_404(application_id)
    if application.student_profile.user_id != current_user.id:
        abort(403)
    if not can_respond_to_offer(application.status):
        flash("There is no pending offer to respond to.", "warning")
        return redirect(url_for("application.detail", application_id=application_id))

    application.status = "offer_declined"
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status="offer_declined", changed_by="student",
        notes="Offer declined by student.",
    ))
    db.session.commit()
    notify(application.internship.company.user_id,
           f"{application.student_profile.full_name} declined the offer for '{application.internship.title}'.",
           category="application", link=url_for("application.detail", application_id=application.id))
    flash("Offer declined.", "info")
    return redirect(url_for("application.detail", application_id=application_id))


@application_bp.route("/resume/<int:resume_id>")
@login_required
def download_resume(resume_id):
    """Authenticated resume access: the student who owns it, a company the
    student has applied to, or an admin. Never served from static/ — files
    live under UPLOAD_FOLDER_RESUMES, outside the public web root."""
    resume = Resume.query.get_or_404(resume_id)
    if not can_view_resume(current_user, resume):
        abort(403)
    directory = os.path.dirname(resume.file_path)
    filename = os.path.basename(resume.file_path)
    return send_from_directory(directory, filename, as_attachment=False,
                                download_name=resume.original_filename)
