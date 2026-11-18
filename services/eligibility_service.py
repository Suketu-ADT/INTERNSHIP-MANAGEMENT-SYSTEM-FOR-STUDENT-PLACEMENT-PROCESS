"""Hard eligibility rules (CGPA / branch / percentage) — plain Python,
never delegated to the AI model. The AI only explains *soft* fit."""


def check_eligibility(student_profile, internship):
    if not internship.eligibility:
        return True, []
    return internship.eligibility.check(student_profile)


def has_already_applied(student_profile, internship):
    from database.models import Application
    return Application.query.filter_by(
        student_profile_id=student_profile.id, internship_id=internship.id
    ).first() is not None


def can_apply(student_profile, internship):
    reasons = []
    if not internship.is_open():
        reasons.append("This internship is no longer accepting applications.")
    if has_already_applied(student_profile, internship):
        reasons.append("You have already applied to this internship.")
    eligible, elig_reasons = check_eligibility(student_profile, internship)
    if not eligible:
        reasons.extend(elig_reasons)
    return len(reasons) == 0, reasons


# Below this point, skill overlap is a SOFT discovery signal only, shown as
# a browse-page indicator - it never feeds back into check_eligibility()/
# can_apply() above, which stay the single, Python-only source of truth for
# hard (CGPA/branch/year) eligibility. The AI layer (matching_service) never
# overrides either of these.
MISSING_SKILLS_THRESHOLD = 50.0


def eligibility_status(student_profile, internship):
    """Three-state discovery indicator: 'not_eligible' (fails hard academic
    criteria), 'missing_skills' (hard-eligible but has less than half of the
    internship's listed required skills), or 'eligible'."""
    hard_eligible, _ = check_eligibility(student_profile, internship)
    if not hard_eligible:
        return "not_eligible"

    required_skills = internship.skills_list()
    if not required_skills:
        return "eligible"

    from services.matching_service import _skill_overlap_percent
    student_skills = [s.skill_name for s in student_profile.skills.all()]
    overlap = _skill_overlap_percent(student_skills, required_skills)
    return "eligible" if overlap >= MISSING_SKILLS_THRESHOLD else "missing_skills"
