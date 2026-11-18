"""Interview scheduling rules, plus the write-path helpers that keep
InterviewHistory (the audit trail) and the parent application's status in
sync with every schedule / reschedule / cancel action."""
from datetime import datetime

from database.models import db, Interview, InterviewHistory, ApplicationStatusHistory


def validate_schedule_datetime(scheduled_at):
    """Returns (ok, error_message). Interviews can never be set in the past."""
    if scheduled_at <= datetime.utcnow():
        return False, "Interview date/time must be in the future."
    return True, None


def has_active_interview(application, exclude_interview_id=None):
    """An application may only have one *currently scheduled* interview at
    a time - reschedule the existing one instead of stacking a second."""
    query = application.interviews.filter(Interview.status == "scheduled")
    if exclude_interview_id is not None:
        query = query.filter(Interview.id != exclude_interview_id)
    return query.first() is not None


def schedule(application, scheduled_at, mode, location_or_link, notes, changed_by):
    interview = Interview(
        application_id=application.id, scheduled_at=scheduled_at, mode=mode,
        location_or_link=location_or_link, notes=notes,
    )
    db.session.add(interview)
    db.session.flush()
    db.session.add(InterviewHistory(
        interview_id=interview.id, action="scheduled", scheduled_at=scheduled_at,
        changed_by=changed_by, notes="Interview scheduled.",
    ))
    return interview


def reschedule(interview, scheduled_at, location_or_link, changed_by):
    interview.scheduled_at = scheduled_at
    if location_or_link:
        interview.location_or_link = location_or_link
    db.session.add(InterviewHistory(
        interview_id=interview.id, action="rescheduled", scheduled_at=scheduled_at,
        changed_by=changed_by,
        notes=f"Rescheduled to {scheduled_at.strftime('%d %b %Y, %I:%M %p')}.",
    ))


def cancel(interview, changed_by):
    """Cancels the interview and, if the application has no other active
    interview, reverts it from 'interview_scheduled' back to 'shortlisted'
    so the company isn't stuck - they can reschedule or move the
    application forward normally."""
    interview.status = "cancelled"
    db.session.add(InterviewHistory(
        interview_id=interview.id, action="cancelled", scheduled_at=interview.scheduled_at,
        changed_by=changed_by, notes="Interview cancelled.",
    ))

    application = interview.application
    if application.status == "interview_scheduled" and not has_active_interview(application, interview.id):
        application.status = "shortlisted"
        db.session.add(ApplicationStatusHistory(
            application_id=application.id, status="shortlisted", changed_by=changed_by,
            notes="Reverted to shortlisted after interview cancellation.",
        ))
