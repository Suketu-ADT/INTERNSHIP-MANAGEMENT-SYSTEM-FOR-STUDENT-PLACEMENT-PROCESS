import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database.models import (
    db, Application, Internship, StudentSkill, AcademicDetails, Resume, Interview, Company, AIAnalysis
)
from forms import StudentProfileForm, AcademicDetailsForm, SkillForm, ResumeUploadForm
from services.resume_service import extract_text, save_upload, sniff_matches_extension
from services.eligibility_service import eligibility_status
from utils.decorators import role_required
from utils.helpers import allowed_file, unique_filename

student_bp = Blueprint("student", __name__)


def _missing_profile_items(profile):
    """What's left to fill in, with a link to go fix it - drives both the
    profile-completion checklist and the new-student onboarding card. Never
    fabricated: every item reflects an actual missing/empty DB field."""
    items = []
    if not profile.academic_details:
        items.append({"label": "Add your academic details", "url": url_for("student.academic")})
    if profile.skills.count() == 0:
        items.append({"label": "Add at least one skill", "url": url_for("student.skills")})
    if profile.resumes.count() == 0:
        items.append({"label": "Upload your resume", "url": url_for("student.resume")})
    if not profile.phone:
        items.append({"label": "Add your contact information", "url": url_for("student.profile")})
    return items


def _cached_match_score(profile_id, internship_id):
    """A previously-computed AI match score for this student+internship, if
    one exists (services/matching_service.match_internship, run on demand
    from the internship detail page) - never computed fresh here, since
    scoring every dashboard internship against Groq on every page load
    would be slow and costly."""
    import json
    latest = (
        AIAnalysis.query.filter_by(student_profile_id=profile_id, internship_id=internship_id,
                                    analysis_type="matching")
        .order_by(AIAnalysis.created_at.desc()).first()
    )
    if not latest:
        return None
    try:
        return json.loads(latest.result_json).get("match_score")
    except (ValueError, TypeError):
        return None


@student_bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    profile = current_user.student_profile

    applications = profile.applications
    total = applications.count()
    pending = applications.filter(Application.status.in_(["pending", "under_review"])).count()
    shortlisted = applications.filter(Application.status == "shortlisted").count()
    selected = applications.filter(Application.status == "selected").count()

    recent_internships = Internship.query.filter_by(status="approved").order_by(
        Internship.posted_at.desc()).limit(6).all()
    recommended = [
        {
            "internship": i,
            "eligibility": eligibility_status(profile, i),
            "match_score": _cached_match_score(profile.id, i.id),
        }
        for i in recent_internships
    ]

    featured_companies = (
        Company.query.filter_by(is_approved=True)
        .join(Internship, Internship.company_id == Company.id)
        .filter(Internship.status == "approved")
        .distinct().order_by(Company.created_at.desc()).limit(6).all()
    )

    recent_applications = applications.order_by(Application.applied_at.desc()).limit(5).all()

    upcoming_interviews = (
        Interview.query.join(Application)
        .filter(Application.student_profile_id == profile.id, Interview.status == "scheduled",
                Interview.scheduled_at >= datetime.utcnow())
        .order_by(Interview.scheduled_at.asc()).limit(5).all()
    )

    missing_profile_items = _missing_profile_items(profile)
    is_new_student = total == 0 and len(missing_profile_items) > 0

    return render_template(
        "student/dashboard.html", profile=profile, total=total, pending=pending,
        shortlisted=shortlisted, selected=selected, recommended=recommended,
        featured_companies=featured_companies,
        recent_applications=recent_applications, upcoming_interviews=upcoming_interviews,
        missing_profile_items=missing_profile_items, is_new_student=is_new_student,
    )


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("student")
def profile():
    student_profile = current_user.student_profile
    form = StudentProfileForm(obj=student_profile)
    if request.method == "GET":
        form.full_name.data = student_profile.full_name
        form.phone.data = student_profile.phone
        form.branch.data = student_profile.branch
        form.year_of_study.data = student_profile.year_of_study
        form.location.data = student_profile.location
        form.bio.data = student_profile.bio

    if form.validate_on_submit():
        student_profile.full_name = form.full_name.data.strip()
        student_profile.phone = form.phone.data
        student_profile.branch = form.branch.data.strip()
        student_profile.year_of_study = form.year_of_study.data
        student_profile.location = form.location.data
        student_profile.bio = form.bio.data

        file = form.profile_photo.data
        if file and allowed_file(file.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            filename = unique_filename(secure_filename(file.filename))
            path = os.path.join(current_app.config["UPLOAD_FOLDER_LOGOS"], filename)
            file.save(path)
            student_profile.profile_photo = filename

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student.profile"))

    return render_template("student/profile.html", form=form, profile=student_profile)


@student_bp.route("/academic", methods=["GET", "POST"])
@login_required
@role_required("student")
def academic():
    student_profile = current_user.student_profile
    academics = student_profile.academic_details or AcademicDetails(student_profile_id=student_profile.id)
    form = AcademicDetailsForm(obj=academics)

    if form.validate_on_submit():
        academics.degree = form.degree.data
        academics.institution = form.institution.data
        academics.cgpa = form.cgpa.data
        academics.percentage_10 = form.percentage_10.data
        academics.percentage_12 = form.percentage_12.data
        academics.graduation_year = form.graduation_year.data
        if academics.id is None:
            db.session.add(academics)
        db.session.commit()
        flash("Academic details saved.", "success")
        return redirect(url_for("student.academic"))

    return render_template("student/academic.html", form=form)


@student_bp.route("/skills", methods=["GET", "POST"])
@login_required
@role_required("student")
def skills():
    student_profile = current_user.student_profile
    form = SkillForm()
    if form.validate_on_submit():
        existing = StudentSkill.query.filter_by(
            student_profile_id=student_profile.id, skill_name=form.skill_name.data.strip()).first()
        if existing:
            flash("This skill is already in your profile.", "warning")
        else:
            db.session.add(StudentSkill(
                student_profile_id=student_profile.id, skill_name=form.skill_name.data.strip(),
                skill_type=form.skill_type.data, proficiency=form.proficiency.data,
            ))
            db.session.commit()
            flash("Skill added.", "success")
        return redirect(url_for("student.skills"))

    all_skills = student_profile.skills.order_by(StudentSkill.skill_type).all()
    return render_template("student/skills.html", form=form, skills=all_skills)


@student_bp.route("/skills/<int:skill_id>/delete", methods=["POST"])
@login_required
@role_required("student")
def delete_skill(skill_id):
    skill = StudentSkill.query.get_or_404(skill_id)
    if skill.student_profile_id != current_user.student_profile.id:
        flash("Not authorized.", "danger")
        return redirect(url_for("student.skills"))
    db.session.delete(skill)
    db.session.commit()
    flash("Skill removed.", "info")
    return redirect(url_for("student.skills"))


@student_bp.route("/resume", methods=["GET", "POST"])
@login_required
@role_required("student")
def resume():
    student_profile = current_user.student_profile
    form = ResumeUploadForm()

    if form.validate_on_submit():
        file = form.resume_file.data
        filename = secure_filename(file.filename)
        if not allowed_file(filename, current_app.config["ALLOWED_RESUME_EXTENSIONS"]):
            flash("Only PDF and DOCX files are allowed.", "danger")
            return redirect(url_for("student.resume"))

        extension = filename.rsplit(".", 1)[1].lower()
        if not sniff_matches_extension(file, extension):
            flash("That file doesn't look like a valid PDF or DOCX. "
                  "Please upload an unmodified resume file.", "danger")
            return redirect(url_for("student.resume"))

        stored_name = unique_filename(filename)
        file_path = save_upload(file, current_app.config["UPLOAD_FOLDER_RESUMES"], stored_name)
        file_size = os.path.getsize(file_path)

        try:
            parsed_text = extract_text(file_path)
        except Exception:
            parsed_text = ""

        resume_record = Resume(
            student_profile_id=student_profile.id, original_filename=filename,
            stored_filename=stored_name, file_path=file_path, file_size=file_size,
            parsed_text=parsed_text,
        )
        db.session.add(resume_record)
        db.session.commit()
        flash("Resume uploaded successfully.", "success")
        return redirect(url_for("student.resume"))

    resumes = student_profile.resumes.order_by(Resume.uploaded_at.desc()).all()
    return render_template("student/resume.html", form=form, resumes=resumes)


@student_bp.route("/resume/<int:resume_id>/delete", methods=["POST"])
@login_required
@role_required("student")
def delete_resume(resume_id):
    resume_record = Resume.query.get_or_404(resume_id)
    if resume_record.student_profile_id != current_user.student_profile.id:
        flash("Not authorized.", "danger")
        return redirect(url_for("student.resume"))
    try:
        if os.path.exists(resume_record.file_path):
            os.remove(resume_record.file_path)
    except OSError:
        pass
    db.session.delete(resume_record)
    db.session.commit()
    flash("Resume deleted.", "info")
    return redirect(url_for("student.resume"))
