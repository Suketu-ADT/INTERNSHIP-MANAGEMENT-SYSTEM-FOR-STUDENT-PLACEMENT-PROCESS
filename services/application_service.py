"""The application status state machine. Every status change in the app
must go through here so a status can never jump out of order (e.g.
'pending' straight to 'selected', or back out of a terminal state)."""

STATUS_LABELS = {
    "pending": "Pending",
    "under_review": "Under Review",
    "shortlisted": "Shortlisted",
    "interview_scheduled": "Interview Scheduled",
    "selected": "Selected",
    "offer_accepted": "Offer Accepted",
    "offer_declined": "Offer Declined",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

# What a company/admin may move an application to, from its current status.
COMPANY_ADMIN_TRANSITIONS = {
    "pending": {"under_review", "rejected"},
    "under_review": {"shortlisted", "rejected"},
    "shortlisted": {"interview_scheduled", "selected", "rejected"},
    "interview_scheduled": {"selected", "rejected"},
}

# A student may withdraw from any of these (anything still "in play").
STUDENT_WITHDRAW_FROM = {"pending", "under_review", "shortlisted", "interview_scheduled"}

# A student may only accept/decline an offer once a company has selected them.
OFFER_RESPONSE_FROM = {"selected"}


def allowed_next_statuses(current_status):
    return COMPANY_ADMIN_TRANSITIONS.get(current_status, set())


def can_company_set_status(current_status, new_status):
    return new_status in allowed_next_statuses(current_status)


def can_withdraw(current_status):
    return current_status in STUDENT_WITHDRAW_FROM


def can_respond_to_offer(current_status):
    return current_status in OFFER_RESPONSE_FROM
