from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField, FloatField,
    IntegerField, DateField, SubmitField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


class StudentRegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password",
                                      validators=[DataRequired(), EqualTo("password")])
    branch = StringField("Branch", validators=[DataRequired(), Length(max=80)])
    year_of_study = SelectField("Year of Study", choices=[
        ("1", "1st Year"), ("2", "2nd Year"), ("3", "3rd Year"), ("4", "4th Year")
    ])
    submit = SubmitField("Create Account")


class CompanyRegisterForm(FlaskForm):
    company_name = StringField("Company Name", validators=[DataRequired(), Length(max=160)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password",
                                      validators=[DataRequired(), EqualTo("password")])
    industry = StringField("Industry", validators=[Optional(), Length(max=120)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Create Account")


class StudentProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=20)])
    branch = StringField("Branch", validators=[DataRequired(), Length(max=80)])
    year_of_study = SelectField("Year of Study", choices=[
        ("1", "1st Year"), ("2", "2nd Year"), ("3", "3rd Year"), ("4", "4th Year")
    ])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=1000)])
    profile_photo = FileField("Profile Photo", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png"])])
    submit = SubmitField("Save Changes")


class AcademicDetailsForm(FlaskForm):
    degree = StringField("Degree", validators=[DataRequired(), Length(max=120)])
    institution = StringField("Institution", validators=[DataRequired(), Length(max=160)])
    cgpa = FloatField("CGPA", validators=[DataRequired(), NumberRange(min=0, max=10)])
    percentage_10 = FloatField("10th Percentage", validators=[Optional(), NumberRange(min=0, max=100)])
    percentage_12 = FloatField("12th Percentage", validators=[Optional(), NumberRange(min=0, max=100)])
    graduation_year = IntegerField("Graduation Year", validators=[Optional(), NumberRange(min=2000, max=2100)])
    submit = SubmitField("Save Academic Details")


class SkillForm(FlaskForm):
    skill_name = StringField("Skill", validators=[DataRequired(), Length(max=80)])
    skill_type = SelectField("Type", choices=[("technical", "Technical"), ("soft", "Soft Skill")])
    proficiency = SelectField("Proficiency", choices=[
        ("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")
    ])
    submit = SubmitField("Add Skill")


class ResumeUploadForm(FlaskForm):
    resume_file = FileField("Resume (PDF or DOCX)", validators=[
        DataRequired(), FileAllowed(["pdf", "docx"], "PDF and DOCX files only")
    ])
    submit = SubmitField("Upload Resume")


class CompanyProfileForm(FlaskForm):
    company_name = StringField("Company Name", validators=[DataRequired(), Length(max=160)])
    industry = StringField("Industry", validators=[Optional(), Length(max=120)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    contact_person = StringField("Contact Person", validators=[Optional(), Length(max=120)])
    contact_phone = StringField("Contact Phone", validators=[Optional(), Length(max=20)])
    logo = FileField("Company Logo", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png"])])
    submit = SubmitField("Save Changes")


class InternshipForm(FlaskForm):
    title = StringField("Internship Title", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=4000)])
    required_skills = StringField("Required Skills (comma separated)", validators=[Optional(), Length(max=500)])
    domain = StringField("Domain", validators=[DataRequired(), Length(max=80)])
    location = StringField("Location", validators=[DataRequired(), Length(max=120)])
    work_mode = SelectField("Work Mode", choices=[
        ("remote", "Remote"), ("hybrid", "Hybrid"), ("onsite", "On-site")
    ])
    stipend = IntegerField("Stipend (per month)", validators=[Optional(), NumberRange(min=0)])
    duration_weeks = IntegerField("Duration (weeks)", validators=[DataRequired(), NumberRange(min=1, max=104)])
    openings = IntegerField("Number of Openings", validators=[DataRequired(), NumberRange(min=1)])
    application_deadline = DateField("Application Deadline", validators=[DataRequired()])

    min_cgpa = FloatField("Minimum CGPA", validators=[Optional(), NumberRange(min=0, max=10)])
    min_percentage = FloatField("Minimum 12th %", validators=[Optional(), NumberRange(min=0, max=100)])
    eligible_branches = StringField("Eligible Branches (comma separated, blank = all)",
                                     validators=[Optional(), Length(max=300)])
    min_year = SelectField("Minimum Year of Study", choices=[
        ("", "Any year"), ("1", "1st Year"), ("2", "2nd Year"), ("3", "3rd Year"), ("4", "4th Year"),
    ], validators=[Optional()])
    submit = SubmitField("Save Internship")


class ApplicationStatusForm(FlaskForm):
    status = SelectField("Status", choices=[
        ("under_review", "Under Review"), ("shortlisted", "Shortlisted"),
        ("interview_scheduled", "Interview Scheduled"), ("selected", "Selected"),
        ("rejected", "Rejected"),
    ])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Update Status")


class InterviewForm(FlaskForm):
    scheduled_at = StringField("Scheduled Date/Time", validators=[DataRequired()])
    mode = SelectField("Mode", choices=[("online", "Online"), ("onsite", "On-site"), ("phone", "Phone")])
    location_or_link = StringField("Location / Meeting Link", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Schedule Interview")


class ChatMessageForm(FlaskForm):
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=1000)])
    submit = SubmitField("Send")
