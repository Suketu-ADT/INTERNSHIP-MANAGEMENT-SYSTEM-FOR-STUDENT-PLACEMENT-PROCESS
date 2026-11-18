from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from database.models import db, Internship, SavedInternship, Company
from services.eligibility_service import check_eligibility, can_apply, has_already_applied, eligibility_status
from utils.decorators import role_required

internship_bp = Blueprint("internship", __name__)

PER_PAGE = 9
SORT_OPTIONS = {
    "newest": Internship.posted_at.desc(),
    "deadline": Internship.application_deadline.asc(),
}


@internship_bp.route("/browse")
@login_required
@role_required("student")
def browse():
    query = Internship.query.filter(Internship.status == "approved").join(Company)

    search = request.args.get("q", "").strip()
    domain = request.args.get("domain", "").strip()
    location = request.args.get("location", "").strip()
    work_mode = request.args.get("work_mode", "").strip()
    min_stipend = request.args.get("min_stipend", type=int)
    eligible_only = request.args.get("eligible_only") == "1"
    sort = request.args.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"
    page = request.args.get("page", 1, type=int)

    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Internship.title.ilike(like), Company.company_name.ilike(like)))
    if domain:
        query = query.filter(Internship.domain == domain)
    if location:
        query = query.filter(Internship.location.ilike(f"%{location}%"))
    if work_mode:
        query = query.filter(Internship.work_mode == work_mode)
    if min_stipend:
        query = query.filter(Internship.stipend >= min_stipend)

    query = query.filter(db.or_(Internship.application_deadline.is_(None),
                                 Internship.application_deadline >= date.today()))
    query = query.order_by(SORT_OPTIONS[sort])

    profile = current_user.student_profile

    if eligible_only:
        # Hard eligibility (CGPA/branch/year) is Python logic (services/eligibility_service.py)
        # and must stay the single source of truth, so it can't be pushed into SQL without
        # duplicating - and risking diverging from - that logic. We page over the
        # already-SQL-filtered id list in Python instead of the whole table.
        matching_ids = [i.id for i in query.all() if check_eligibility(profile, i)[0]]
        total = len(matching_ids)
        start = (page - 1) * PER_PAGE
        page_ids = matching_ids[start:start + PER_PAGE]
        page_items = Internship.query.filter(Internship.id.in_(page_ids)).all() if page_ids else []
        page_items.sort(key=lambda i: page_ids.index(i.id))
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    else:
        # The common path: real database-level LIMIT/OFFSET pagination.
        pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)
        page_items = pagination.items
        total = pagination.total
        total_pages = pagination.pages or 1

    saved_ids = {s.internship_id for s in profile.saved_internships.all()}
    domains = [d[0] for d in db.session.query(Internship.domain).filter(
        Internship.status == "approved").distinct() if d[0]]

    eligibility_map = {i.id: eligibility_status(profile, i) for i in page_items}

    return render_template(
        "student/browse_internships.html", internships=page_items, saved_ids=saved_ids,
        domains=domains, page=page, total_pages=total_pages, total=total,
        eligibility_map=eligibility_map, sort=sort,
        filters={"q": search, "domain": domain, "location": location, "work_mode": work_mode,
                 "min_stipend": min_stipend or "", "eligible_only": "1" if eligible_only else "",
                 "sort": sort},
    )


@internship_bp.route("/<int:internship_id>")
@login_required
@role_required("student")
def detail(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    profile = current_user.student_profile
    eligible, reasons = check_eligibility(profile, internship)
    already_applied = has_already_applied(profile, internship)
    is_saved = SavedInternship.query.filter_by(
        student_profile_id=profile.id, internship_id=internship.id).first() is not None
    can_apply_now, apply_reasons = can_apply(profile, internship)

    return render_template(
        "student/internship_detail.html", internship=internship, eligible=eligible,
        reasons=reasons, already_applied=already_applied, is_saved=is_saved,
        can_apply_now=can_apply_now, apply_reasons=apply_reasons,
    )


@internship_bp.route("/<int:internship_id>/save", methods=["POST"])
@login_required
@role_required("student")
def toggle_save(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    profile = current_user.student_profile
    existing = SavedInternship.query.filter_by(
        student_profile_id=profile.id, internship_id=internship.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        saved = False
    else:
        db.session.add(SavedInternship(student_profile_id=profile.id, internship_id=internship.id))
        db.session.commit()
        saved = True

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"saved": saved})
    flash("Saved." if saved else "Removed from saved internships.", "success")
    return redirect(request.referrer or url_for("internship.browse"))


@internship_bp.route("/saved")
@login_required
@role_required("student")
def saved_list():
    profile = current_user.student_profile
    saved = profile.saved_internships.order_by(SavedInternship.saved_at.desc()).all()
    return render_template("student/saved_internships.html", saved=saved)
