import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from database.models import db, Internship, AIAnalysis, ChatMessage
from forms import ChatMessageForm
from services import groq_service, matching_service
from services.eligibility_service import check_eligibility
from utils.decorators import role_required

ai_bp = Blueprint("ai", __name__)


def _ai_unavailable_response(redirect_endpoint):
    flash("AI features are not configured yet. Add GROQ_API_KEY to your .env file to enable them.", "warning")
    return redirect(url_for(redirect_endpoint))


def _ai_failed_response(redirect_endpoint):
    flash("The AI service is temporarily unavailable. Please try again in a moment.", "danger")
    return redirect(url_for(redirect_endpoint))


@ai_bp.route("/resume-analyzer", methods=["GET", "POST"])
@login_required
@role_required("student")
def resume_analyzer():
    profile = current_user.student_profile
    resume_record = profile.active_resume()

    if request.method == "POST":
        if not groq_service.is_configured():
            return _ai_unavailable_response("ai.resume_analyzer")
        if not resume_record or not resume_record.parsed_text:
            flash("Upload a resume first so it can be analyzed.", "warning")
            return redirect(url_for("student.resume"))

        try:
            result = matching_service.analyze_resume(resume_record.parsed_text)
        except groq_service.GroqNotConfigured:
            return _ai_unavailable_response("ai.resume_analyzer")
        except groq_service.AIServiceError:
            return _ai_failed_response("ai.resume_analyzer")

        if result is None:
            flash("The AI analysis could not be generated right now. Please try again.", "danger")
            return redirect(url_for("ai.resume_analyzer"))

        analysis = AIAnalysis(student_profile_id=profile.id, analysis_type="resume_analysis",
                               result_json=json.dumps(result))
        db.session.add(analysis)
        db.session.commit()
        return redirect(url_for("ai.resume_analyzer"))

    latest = (
        AIAnalysis.query.filter_by(student_profile_id=profile.id, analysis_type="resume_analysis")
        .order_by(AIAnalysis.created_at.desc()).first()
    )
    result = json.loads(latest.result_json) if latest else None
    return render_template("student/resume_analyzer.html", result=result, resume_record=resume_record,
                            ai_configured=groq_service.is_configured())


@ai_bp.route("/match/<int:internship_id>", methods=["POST"])
@login_required
@role_required("student")
def match(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    profile = current_user.student_profile

    if not groq_service.is_configured():
        return jsonify({"error": "AI not configured. Add GROQ_API_KEY to your .env file."}), 503

    eligible, _ = check_eligibility(profile, internship)
    resume_record = profile.active_resume()
    resume_text = resume_record.parsed_text if resume_record else ""

    try:
        result = matching_service.match_internship(profile, internship, resume_text)
    except groq_service.GroqNotConfigured:
        return jsonify({"error": "AI not configured."}), 503
    except groq_service.AIServiceError:
        return jsonify({"error": "The AI service is temporarily unavailable. Please try again."}), 502

    if result is None:
        return jsonify({"error": "Could not generate match analysis. Try again."}), 502

    analysis = AIAnalysis(student_profile_id=profile.id, internship_id=internship.id,
                           analysis_type="matching", result_json=json.dumps(result))
    db.session.add(analysis)
    db.session.commit()

    result["hard_eligible"] = eligible
    return jsonify(result)


@ai_bp.route("/recommendations")
@login_required
@role_required("student")
def recommendations():
    profile = current_user.student_profile

    if not groq_service.is_configured():
        return render_template("student/ai_recommendations.html", recommendations=None, ai_configured=False)

    candidates = [i for i in Internship.query.filter_by(status="approved").all()
                  if check_eligibility(profile, i)[0]]

    try:
        raw_recs = matching_service.recommend_internships(profile, candidates)
    except groq_service.GroqNotConfigured:
        return render_template("student/ai_recommendations.html", recommendations=None, ai_configured=False)
    except groq_service.AIServiceError:
        flash("The AI service is temporarily unavailable. Please try again in a moment.", "danger")
        return render_template("student/ai_recommendations.html", recommendations=None, ai_configured=True)

    by_id = {i.id: i for i in candidates}
    recommendations_list = []
    for rec in raw_recs:
        internship = by_id.get(rec["id"])
        if internship:
            recommendations_list.append({"internship": internship, "reasons": rec["reasons"]})

    return render_template("student/ai_recommendations.html", recommendations=recommendations_list,
                            ai_configured=True)


@ai_bp.route("/skill-gap/<int:internship_id>")
@login_required
@role_required("student")
def skill_gap(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    profile = current_user.student_profile
    student_skills = [s.skill_name for s in profile.skills.all()]

    if not groq_service.is_configured():
        return jsonify({"error": "AI not configured."}), 503

    try:
        result = matching_service.skill_gap_analysis(student_skills, internship)
    except groq_service.GroqNotConfigured:
        return jsonify({"error": "AI not configured."}), 503
    except groq_service.AIServiceError:
        return jsonify({"error": "The AI service is temporarily unavailable. Please try again."}), 502

    return jsonify(result)


def _load_chat_history(profile, limit=20):
    """Chat history is persisted per-student in the database (ChatMessage),
    not the session cookie, so it survives across devices and logins and
    is isolated to this student by student_profile_id."""
    rows = (
        ChatMessage.query.filter_by(student_profile_id=profile.id)
        .order_by(ChatMessage.created_at.desc()).limit(limit).all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


@ai_bp.route("/career-assistant", methods=["GET", "POST"])
@login_required
@role_required("student")
def career_assistant():
    profile = current_user.student_profile
    form = ChatMessageForm()

    if form.validate_on_submit():
        if not groq_service.is_configured():
            return _ai_unavailable_response("ai.career_assistant")
        user_message = form.message.data.strip()
        history = _load_chat_history(profile)
        try:
            reply = matching_service.career_chat(profile, history, user_message)
        except groq_service.GroqNotConfigured:
            return _ai_unavailable_response("ai.career_assistant")
        except groq_service.AIServiceError:
            return _ai_failed_response("ai.career_assistant")

        db.session.add(ChatMessage(student_profile_id=profile.id, role="user", content=user_message))
        db.session.add(ChatMessage(student_profile_id=profile.id, role="assistant", content=reply))
        db.session.commit()
        return redirect(url_for("ai.career_assistant"))

    history = _load_chat_history(profile)
    return render_template("student/career_assistant.html", form=form, history=history,
                            ai_configured=groq_service.is_configured())


@ai_bp.route("/career-assistant/clear", methods=["POST"])
@login_required
@role_required("student")
def clear_chat():
    ChatMessage.query.filter_by(student_profile_id=current_user.student_profile.id).delete()
    db.session.commit()
    return redirect(url_for("ai.career_assistant"))
