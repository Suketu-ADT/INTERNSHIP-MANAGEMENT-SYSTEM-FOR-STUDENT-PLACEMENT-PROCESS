from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Core identity
# ---------------------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)  # student | company | admin
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student_profile = db.relationship("StudentProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    company = db.relationship("Company", backref="user", uselist=False, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", backref="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active(self):
        return self.is_active_account

    def display_name(self):
        if self.role == "student" and self.student_profile:
            return self.student_profile.full_name
        if self.role == "company" and self.company:
            return self.company.company_name
        return self.email


# ---------------------------------------------------------------------------
# Student side
# ---------------------------------------------------------------------------
class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    branch = db.Column(db.String(80))
    year_of_study = db.Column(db.String(20))
    bio = db.Column(db.Text)
    location = db.Column(db.String(120))
    profile_photo = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    academic_details = db.relationship("AcademicDetails", backref="student_profile", uselist=False,
                                        cascade="all, delete-orphan")
    skills = db.relationship("StudentSkill", backref="student_profile", cascade="all, delete-orphan", lazy="dynamic")
    resumes = db.relationship("Resume", backref="student_profile", cascade="all, delete-orphan", lazy="dynamic")
    applications = db.relationship("Application", backref="student_profile", cascade="all, delete-orphan",
                                    lazy="dynamic")
    saved_internships = db.relationship("SavedInternship", backref="student_profile", cascade="all, delete-orphan",
                                         lazy="dynamic")
    chat_messages = db.relationship("ChatMessage", backref="student_profile", cascade="all, delete-orphan",
                                     lazy="dynamic")

    def active_resume(self):
        return self.resumes.order_by(Resume.uploaded_at.desc()).first()

    def profile_completion(self):
        fields = [self.full_name, self.phone, self.branch, self.year_of_study, self.bio, self.location]
        filled = sum(1 for f in fields if f)
        total = len(fields) + 2  # + academic details + at least one skill
        if self.academic_details:
            filled += 1
        if self.skills.count() > 0:
            filled += 1
        return round((filled / total) * 100)


class AcademicDetails(db.Model):
    __tablename__ = "academic_details"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), unique=True, nullable=False)

    degree = db.Column(db.String(120))
    institution = db.Column(db.String(160))
    cgpa = db.Column(db.Float)
    percentage_10 = db.Column(db.Float)
    percentage_12 = db.Column(db.Float)
    graduation_year = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentSkill(db.Model):
    __tablename__ = "student_skills"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)

    skill_name = db.Column(db.String(80), nullable=False)
    skill_type = db.Column(db.String(20), nullable=False, default="technical")  # technical | soft
    proficiency = db.Column(db.String(20), default="intermediate")  # beginner|intermediate|advanced

    __table_args__ = (db.UniqueConstraint("student_profile_id", "skill_name", name="uq_student_skill"),)


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    parsed_text = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Company side
# ---------------------------------------------------------------------------
class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    company_name = db.Column(db.String(160), nullable=False)
    industry = db.Column(db.String(120))
    website = db.Column(db.String(255))
    description = db.Column(db.Text)
    logo = db.Column(db.String(255))
    contact_person = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))

    is_approved = db.Column(db.Boolean, default=False, nullable=False, index=True)
    approved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # True only for companies created by the demo-data seeder (database/seed_demo.py).
    # Never set for a real company registration - lets the UI label them clearly
    # and lets admins wipe seeded data without touching real records.
    is_demo = db.Column(db.Boolean, default=False, nullable=False, index=True)

    internships = db.relationship("Internship", backref="company", cascade="all, delete-orphan", lazy="dynamic")


# ---------------------------------------------------------------------------
# Internship & eligibility
# ---------------------------------------------------------------------------
class Internship(db.Model):
    __tablename__ = "internships"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)

    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text)  # comma separated
    domain = db.Column(db.String(80), index=True)
    location = db.Column(db.String(120))
    work_mode = db.Column(db.String(20), default="onsite")  # remote|hybrid|onsite
    stipend = db.Column(db.Integer, default=0)
    duration_weeks = db.Column(db.Integer)
    openings = db.Column(db.Integer, default=1)
    application_deadline = db.Column(db.Date)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # status: pending_approval | approved | rejected | closed
    status = db.Column(db.String(20), default="pending_approval", nullable=False, index=True)

    # Mirrors Company.is_demo - set only by the seeder, for the same reasons.
    is_demo = db.Column(db.Boolean, default=False, nullable=False, index=True)

    eligibility = db.relationship("EligibilityCriteria", backref="internship", uselist=False,
                                   cascade="all, delete-orphan")
    applications = db.relationship("Application", backref="internship", cascade="all, delete-orphan",
                                    lazy="dynamic")
    saved_by = db.relationship("SavedInternship", backref="internship", cascade="all, delete-orphan", lazy="dynamic")

    def skills_list(self):
        return [s.strip() for s in (self.required_skills or "").split(",") if s.strip()]

    def is_open(self):
        from datetime import date
        if self.status != "approved":
            return False
        if self.application_deadline and self.application_deadline < date.today():
            return False
        return True


class EligibilityCriteria(db.Model):
    __tablename__ = "eligibility_criteria"

    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id"), unique=True, nullable=False)

    min_cgpa = db.Column(db.Float, default=0)
    min_percentage = db.Column(db.Float, default=0)
    eligible_branches = db.Column(db.Text)  # comma separated, empty = all branches
    min_year = db.Column(db.String(20))

    def branches_list(self):
        return [b.strip() for b in (self.eligible_branches or "").split(",") if b.strip()]

    def check(self, student_profile):
        academics = student_profile.academic_details
        if not academics:
            return False, ["No academic details on file"]
        reasons = []
        if self.min_cgpa and (academics.cgpa or 0) < self.min_cgpa:
            reasons.append(f"CGPA {academics.cgpa or 0} below required {self.min_cgpa}")
        if self.min_percentage and (academics.percentage_12 or 0) < self.min_percentage:
            reasons.append(f"12th % {academics.percentage_12 or 0} below required {self.min_percentage}")
        branches = self.branches_list()
        if branches and student_profile.branch not in branches:
            reasons.append(f"Branch '{student_profile.branch}' not in eligible branches")
        if self.min_year:
            try:
                required_year = int(self.min_year)
                student_year = int(student_profile.year_of_study)
            except (TypeError, ValueError):
                required_year = None
                student_year = None
            if required_year is not None and (student_year is None or student_year < required_year):
                reasons.append(
                    f"Year of study {student_profile.year_of_study or 'unknown'} "
                    f"below required year {self.min_year}"
                )
        return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
class Application(db.Model):
    __tablename__ = "applications"

    STATUSES = [
        "pending", "under_review", "shortlisted", "interview_scheduled", "selected",
        "offer_accepted", "offer_declined", "rejected", "withdrawn",
    ]

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id"), nullable=False, index=True)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"))

    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resume = db.relationship("Resume")
    status_history = db.relationship("ApplicationStatusHistory", backref="application",
                                      cascade="all, delete-orphan", lazy="dynamic",
                                      order_by="ApplicationStatusHistory.changed_at")
    interviews = db.relationship("Interview", backref="application", cascade="all, delete-orphan", lazy="dynamic")
    feedback_entries = db.relationship("Feedback", backref="application", cascade="all, delete-orphan",
                                        lazy="dynamic")

    __table_args__ = (db.UniqueConstraint("student_profile_id", "internship_id", name="uq_student_internship"),)


class ApplicationStatusHistory(db.Model):
    __tablename__ = "application_status_history"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)

    status = db.Column(db.String(30), nullable=False)
    changed_by = db.Column(db.String(20))  # student | company | admin | system
    notes = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedInternship(db.Model):
    __tablename__ = "saved_internships"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id"), nullable=False, index=True)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("student_profile_id", "internship_id", name="uq_saved_internship"),)


class Interview(db.Model):
    __tablename__ = "interviews"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)

    scheduled_at = db.Column(db.DateTime, nullable=False)
    mode = db.Column(db.String(20), default="online")  # online|onsite|phone
    location_or_link = db.Column(db.String(255))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="scheduled")  # scheduled|completed|cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    history = db.relationship("InterviewHistory", backref="interview", cascade="all, delete-orphan",
                               lazy="dynamic", order_by="InterviewHistory.changed_at")


class InterviewHistory(db.Model):
    """Audit trail of every scheduling/reschedule/cancellation event for an
    interview, mirroring ApplicationStatusHistory's pattern."""
    __tablename__ = "interview_history"

    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id"), nullable=False, index=True)

    action = db.Column(db.String(20), nullable=False)  # scheduled | rescheduled | cancelled
    scheduled_at = db.Column(db.DateTime, nullable=False)  # the time it was set to at this event
    changed_by = db.Column(db.String(20))  # company | admin
    notes = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, index=True)

    given_by = db.Column(db.String(20))  # company | admin
    rating = db.Column(db.Integer)  # 1-5
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Notifications & AI
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    message = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(30), default="general")  # application|interview|approval|system
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AIAnalysis(db.Model):
    __tablename__ = "ai_analysis"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internships.id"), nullable=True, index=True)

    analysis_type = db.Column(db.String(30), nullable=False)  # resume_analysis|matching|recommendation
    result_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    """Persists the AI career assistant conversation per student, so it
    survives across devices/sessions instead of living only in a cookie."""
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    student_profile_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)

    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
