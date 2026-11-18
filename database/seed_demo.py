"""Seeds clearly-labelled DEMO companies and internships so a fresh install
has real content to show on the landing page and student dashboard, instead
of being empty.

Design constraints (see the "FINAL REVIEW" task for the full list):
  - Every record this module creates has is_demo=True, so it is always
    distinguishable from a real company/internship and can be removed
    without touching real data (see remove_demo_data() / admin.demo_data).
  - Fictional company names only; emails/websites use the IANA-reserved
    example.com domain (RFC 2606), never a real company's identity.
  - Idempotent: safe to call on every app startup. Skipped entirely once any
    demo company exists, and each record is additionally get-or-created by
    its unique email, so a partially-seeded run can be re-run safely.
  - This module NEVER touches non-demo rows.
"""
import os
from datetime import date, datetime, timedelta

from database.models import (
    db, User, Company, Internship, EligibilityCriteria, StudentProfile, AcademicDetails, StudentSkill,
    Resume, Application, ApplicationStatusHistory, Interview, InterviewHistory,
)
from services.notification_service import notify

DEMO_PASSWORD = "Demo@1234"
DEMO_STUDENT_EMAIL = "demo.student@example.com"
DEMO_ADMIN_EMAIL = "demo.admin@example.com"
DEMO_RESUME_FILENAME = "demo_student_resume.pdf"

DEMO_COMPANIES = [
    {
        "slug": "novatech", "name": "NovaTech Solutions", "industry": "Software Development",
        "location": "Bengaluru, India",
        "description": "A fictional software product company used only for demo purposes, "
                        "building web and mobile applications for other businesses.",
    },
    {
        "slug": "blueorbit", "name": "BlueOrbit Analytics", "industry": "Data & Analytics",
        "location": "Pune, India",
        "description": "A fictional data analytics company (demo data) that helps "
                        "organizations turn raw data into dashboards and reports.",
    },
    {
        "slug": "codecraftlabs", "name": "CodeCraft Labs", "industry": "Software Development",
        "location": "Hyderabad, India",
        "description": "A fictional software engineering studio (demo data) specializing "
                        "in backend systems and quality engineering.",
    },
    {
        "slug": "finedge", "name": "FinEdge Systems", "industry": "Financial Technology",
        "location": "Mumbai, India",
        "description": "A fictional fintech company (demo data) building tools for "
                        "digital payments and financial analysis.",
    },
    {
        "slug": "cloudspring", "name": "CloudSpring Technologies", "industry": "Cloud Infrastructure",
        "location": "Remote",
        "description": "A fictional cloud infrastructure and security company (demo data) "
                        "offering managed cloud and DevSecOps services.",
    },
    {
        "slug": "pixelpeak", "name": "PixelPeak Digital", "industry": "Design & UI/UX",
        "location": "Bengaluru, India",
        "description": "A fictional digital design studio (demo data) focused on product "
                        "design and front-end experience.",
    },
    {
        "slug": "datanest", "name": "DataNest Technologies", "industry": "Data Engineering",
        "location": "Chennai, India",
        "description": "A fictional data engineering company (demo data) building data "
                        "pipelines and warehousing solutions.",
    },
    {
        "slug": "quantumbyte", "name": "QuantumByte Innovations", "industry": "Artificial Intelligence",
        "location": "Remote",
        "description": "A fictional AI/ML research-driven company (demo data) building "
                        "applied machine learning products.",
    },
]

# (company_slug, title, skills, description, domain, location, work_mode, stipend,
#  duration_weeks, min_cgpa, eligible_branches, min_year, openings)
DEMO_INTERNSHIPS = [
    ("novatech", "Python Developer Intern",
     "Python, Flask, SQL, Git",
     "Work with the backend team building and testing REST APIs for an internal product, "
     "under the guidance of a senior engineer.",
     "Software", "Bengaluru, India", "hybrid", 15000, 8, 7.0, "Computer Science, Information Technology", "2", 3),
    ("novatech", "Full Stack Developer Intern",
     "JavaScript, React, Node.js, SQL",
     "Build features end-to-end across a React front end and a Node.js API, "
     "working closely with product and design.",
     "Software", "Bengaluru, India", "onsite", 18000, 12, 7.5, "Computer Science, Information Technology", "3", 2),
    ("novatech", "Mobile App Developer Intern",
     "Flutter, Dart, REST APIs",
     "Assist in building and testing cross-platform mobile screens for a consumer app, "
     "with code review support from the mobile team.",
     "Software", "Bengaluru, India", "remote", 12000, 8, 6.5, "", "2", 2),
    ("blueorbit", "Data Analyst Intern",
     "SQL, Excel, Python, Power BI",
     "Help the analytics team clean datasets, build reporting dashboards, and summarize "
     "findings for internal stakeholders.",
     "Data Analytics", "Pune, India", "hybrid", 12000, 10, 7.0, "", "2", 3),
    ("codecraftlabs", "Backend Developer Intern",
     "Java, Spring Boot, MySQL",
     "Contribute to backend services for an internal tooling platform, writing unit tests "
     "and fixing small bugs alongside the engineering team.",
     "Software", "Hyderabad, India", "onsite", 14000, 8, 7.0, "Computer Science, Electronics", "3", 2),
    ("codecraftlabs", "QA/Automation Testing Intern",
     "Selenium, Python, Manual Testing",
     "Write and run automated test scripts for a web application and help triage "
     "reported bugs with the QA team.",
     "Quality Assurance", "Hyderabad, India", "remote", 10000, 8, 6.5, "", "2", 2),
    ("finedge", "Business Analyst Intern",
     "Excel, SQL, Communication, Documentation",
     "Support the product team by gathering requirements, documenting workflows, and "
     "preparing analysis for upcoming fintech features.",
     "Business Analysis", "Mumbai, India", "onsite", 13000, 10, 7.0, "", "3", 2),
    ("cloudspring", "Cloud Engineer Intern",
     "AWS, Linux, Docker, Networking Basics",
     "Assist the infrastructure team with configuring cloud environments and monitoring "
     "basic deployments under supervision.",
     "Cloud Computing", "Remote", "remote", 16000, 12, 7.5, "Computer Science, Information Technology", "3", 2),
    ("cloudspring", "Cybersecurity Intern",
     "Networking Basics, Linux, Security Fundamentals",
     "Support the security team with vulnerability scanning exercises and documentation "
     "of findings in a controlled, supervised environment.",
     "Cybersecurity", "Remote", "remote", 15000, 10, 7.5, "Computer Science, Information Technology", "3", 2),
    ("pixelpeak", "UI/UX Design Intern",
     "Figma, Wireframing, User Research",
     "Help design wireframes and prototypes for client projects and participate in "
     "user-feedback review sessions.",
     "Design", "Bengaluru, India", "hybrid", 10000, 8, 6.5, "", "2", 2),
    ("pixelpeak", "Frontend Developer Intern",
     "HTML, CSS, JavaScript, React",
     "Translate design mockups into responsive front-end components and collaborate "
     "with designers on polish and accessibility.",
     "Software", "Bengaluru, India", "hybrid", 13000, 8, 6.5, "", "2", 3),
    ("datanest", "Data Engineering Intern",
     "Python, SQL, Apache Spark Basics, ETL",
     "Help build and test simple ETL pipelines for internal data warehousing projects "
     "with guidance from a senior data engineer.",
     "Data Engineering", "Chennai, India", "onsite", 14000, 10, 7.5, "Computer Science, Information Technology", "3", 2),
    ("quantumbyte", "AI/ML Intern",
     "Python, Machine Learning, scikit-learn, Pandas",
     "Work on a supervised learning experiment under mentorship, from data preparation "
     "to evaluating model results.",
     "Artificial Intelligence", "Remote", "remote", 18000, 12, 8.0, "Computer Science, Electronics", "3", 2),
    ("quantumbyte", "Machine Learning Research Intern",
     "Python, Deep Learning, PyTorch, Research Writing",
     "Assist a research mentor in running small ML experiments and summarizing results "
     "in short written reports.",
     "Artificial Intelligence", "Remote", "remote", 20000, 12, 8.0, "Computer Science", "4", 1),
]

# (company_slug, internship_title, target_status, days_ago_applied) - spread across 6 of the
# 8 demo companies so logging into any demo company account shows at least one real applicant
# to review, not an empty "no applications yet" screen. Every status here is reached through
# the exact same state machine (services/application_service.py) real applications go through -
# never an invented status - so the demo data matches what a real application would look like.
DEMO_APPLICATIONS = [
    ("novatech", "Python Developer Intern", "pending", 2),
    ("blueorbit", "Data Analyst Intern", "under_review", 6),
    ("codecraftlabs", "Backend Developer Intern", "shortlisted", 9),
    ("pixelpeak", "UI/UX Design Intern", "interview_scheduled", 12),
    ("quantumbyte", "AI/ML Intern", "selected", 15),
    ("datanest", "Data Engineering Intern", "rejected", 10),
]

DEMO_RESUME_TEXT = """Demo Student
demo.student@example.com | Bengaluru, India

Education
B.Tech in Computer Science, Demo Institute of Technology (CGPA: 8.2)

Skills
Python, SQL, React, Communication

Projects
- Built a small Flask web application for a class project, including a REST API and a SQLite database.
- Contributed to a group project implementing a basic recommendation algorithm in Python.

Note
This is a demo resume, generated by the platform's demo-data seeder to showcase the
AI Resume Analyzer and AI Match features. It is not a real person's resume.
"""


def _get_or_create_user(email, role):
    user = User.query.filter_by(email=email).first()
    if user:
        return user, False
    user = User(email=email, role=role)
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()
    return user, True


def _pdf_escape(text):
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _build_minimal_pdf(lines):
    """Builds a small, structurally-valid single-page PDF (correct xref
    table, computed from real byte offsets) containing the given lines of
    text - with no external dependency (reportlab etc. isn't in
    requirements.txt, and this is the only place a PDF needs to be
    generated from scratch, so it isn't worth adding one for). Used only
    for the seeded demo student's resume, so the AI Resume Analyzer /
    AI Match features have something real to run against out of the box."""
    content_lines = ["BT", "/F1 11 Tf", "72 740 Td"]
    for i, line in enumerate(lines):
        if i > 0:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(out)


def seed_demo_data():
    """Idempotent: does nothing once any demo company already exists."""
    if Company.query.filter_by(is_demo=True).first() is not None:
        return

    companies_by_slug = {}
    for spec in DEMO_COMPANIES:
        email = f"hr@{spec['slug']}.example.com"
        user, _ = _get_or_create_user(email, "company")
        company = Company.query.filter_by(user_id=user.id).first()
        if company is None:
            company = Company(
                user_id=user.id, company_name=spec["name"], industry=spec["industry"],
                website=f"https://{spec['slug']}.example.com", description=spec["description"],
                is_approved=True, is_demo=True,
            )
            db.session.add(company)
            db.session.flush()
        companies_by_slug[spec["slug"]] = company

    internships_by_key = {}
    for (slug, title, skills, description, domain, location, work_mode, stipend,
         duration_weeks, min_cgpa, eligible_branches, min_year, openings) in DEMO_INTERNSHIPS:
        company = companies_by_slug[slug]
        internship = Internship.query.filter_by(company_id=company.id, title=title).first()
        if internship is None:
            internship = Internship(
                company_id=company.id, title=title, description=description, required_skills=skills,
                domain=domain, location=location, work_mode=work_mode, stipend=stipend,
                duration_weeks=duration_weeks, openings=openings,
                application_deadline=date.today() + timedelta(days=45),
                status="approved", is_demo=True,
            )
            db.session.add(internship)
            db.session.flush()
            db.session.add(EligibilityCriteria(
                internship_id=internship.id, min_cgpa=min_cgpa, eligible_branches=eligible_branches,
                min_year=min_year or None,
            ))
        internships_by_key[(slug, title)] = internship

    profile, resume = _seed_demo_student()
    if profile is not None:
        _seed_demo_applications(profile, resume, internships_by_key)
    _seed_demo_admin()
    db.session.commit()


def _seed_demo_student():
    """One ready-to-explore demo student account, complete with a resume and
    a few in-progress applications (see _seed_demo_applications), so the
    evaluator can log in and see a populated dashboard without registering
    and filling a profile by hand first. Fictional person, reserved
    example.com email. Returns (profile, resume), or (None, None) if the
    account already existed (nothing further to seed)."""
    user, created = _get_or_create_user(DEMO_STUDENT_EMAIL, "student")
    if not created:
        return None, None
    profile = StudentProfile(
        user_id=user.id, full_name="Demo Student", branch="Computer Science",
        year_of_study="3", location="Bengaluru, India",
        bio="Demo account for evaluating the platform.",
    )
    db.session.add(profile)
    db.session.flush()
    db.session.add(AcademicDetails(
        student_profile_id=profile.id, degree="B.Tech", institution="Demo Institute of Technology",
        cgpa=8.2, percentage_10=88, percentage_12=85, graduation_year=date.today().year + 1,
    ))
    for name, skill_type in (("Python", "technical"), ("SQL", "technical"), ("React", "technical"),
                              ("Communication", "soft")):
        db.session.add(StudentSkill(student_profile_id=profile.id, skill_name=name, skill_type=skill_type))

    resume = _write_demo_resume(profile.id)
    return profile, resume


def _write_demo_resume(profile_id):
    from flask import current_app

    pdf_bytes = _build_minimal_pdf(DEMO_RESUME_TEXT.splitlines())
    upload_dir = current_app.config["UPLOAD_FOLDER_RESUMES"]
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, DEMO_RESUME_FILENAME)
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    resume = Resume(
        student_profile_id=profile_id, original_filename="demo_student_resume.pdf",
        stored_filename=DEMO_RESUME_FILENAME, file_path=file_path, file_size=len(pdf_bytes),
        parsed_text=DEMO_RESUME_TEXT,
    )
    db.session.add(resume)
    db.session.flush()
    return resume


_STATUS_SEQUENCE = ["pending", "under_review", "shortlisted", "interview_scheduled", "selected"]


def _seed_demo_applications(profile, resume, internships_by_key):
    """Walks each demo application through the exact same status sequence
    services/application_service.py allows for a real one, writing a
    history row for every step (and an interview + notifications for the
    one that reaches interview_scheduled) - so every demo account's
    dashboard, applicant list and timeline looks like real, in-progress
    activity instead of empty placeholders."""
    for slug, title, target_status, days_ago in DEMO_APPLICATIONS:
        internship = internships_by_key.get((slug, title))
        if internship is None:
            continue

        applied_at = datetime.utcnow() - timedelta(days=days_ago)
        application = Application(
            student_profile_id=profile.id, internship_id=internship.id,
            resume_id=resume.id if resume else None, status=target_status, applied_at=applied_at,
        )
        db.session.add(application)
        db.session.flush()

        if target_status == "rejected":
            steps = ["pending", "under_review", "rejected"]
        else:
            steps = _STATUS_SEQUENCE[:_STATUS_SEQUENCE.index(target_status) + 1]

        for i, status in enumerate(steps):
            changed_by = "student" if status == "pending" else "company"
            db.session.add(ApplicationStatusHistory(
                application_id=application.id, status=status, changed_by=changed_by,
                changed_at=applied_at + timedelta(days=i),
                notes="Application submitted." if status == "pending" else None,
            ))

        if target_status == "interview_scheduled":
            scheduled_at = datetime.utcnow() + timedelta(days=4)
            interview = Interview(
                application_id=application.id, scheduled_at=scheduled_at, mode="online",
                location_or_link="https://meet.example.com/demo-interview", status="scheduled",
            )
            db.session.add(interview)
            db.session.flush()
            db.session.add(InterviewHistory(
                interview_id=interview.id, action="scheduled", scheduled_at=scheduled_at,
                changed_by="company", notes="Interview scheduled.",
            ))

    db.session.flush()
    notify(profile.user_id, "You have 6 applications in progress - check your dashboard for updates.",
           category="application")


def _seed_demo_admin():
    """A documented admin login that isn't the real ADMIN_EMAIL/ADMIN_PASSWORD
    from .env, so an evaluator can explore the placement-office side without
    needing that real credential. Admin has no profile table to populate -
    the dashboards it sees are simply the live, demo-seeded data above."""
    _get_or_create_user(DEMO_ADMIN_EMAIL, "admin")


def remove_demo_data():
    """Deletes every is_demo=True company (cascades to its internships,
    applications, interviews, etc.), the seeded demo student account (and
    its resume file on disk), and the demo admin account. Never touches a
    record that wasn't created by seed_demo_data()."""
    demo_student_user = User.query.filter_by(email=DEMO_STUDENT_EMAIL, role="student").first()
    resume_path = None
    if demo_student_user and demo_student_user.student_profile:
        resume = demo_student_user.student_profile.resumes.first()
        if resume:
            resume_path = resume.file_path

    for company in Company.query.filter_by(is_demo=True).all():
        db.session.delete(company.user)
    if demo_student_user:
        db.session.delete(demo_student_user)
    demo_admin_user = User.query.filter_by(email=DEMO_ADMIN_EMAIL, role="admin").first()
    if demo_admin_user:
        db.session.delete(demo_admin_user)
    db.session.commit()

    if resume_path:
        try:
            if os.path.exists(resume_path):
                os.remove(resume_path)
        except OSError:
            pass
