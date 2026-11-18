"""Deterministic unit tests for the resume-scoring and internship-matching
math in services/matching_service.py. These never call Groq - they test
the pure Python validation/combination logic directly."""
from services.matching_service import (
    _validate_resume_analysis, _skill_overlap_percent, _resume_similarity_percent,
    _validate_match_result, MATCH_WEIGHTS, REQUIRED_BREAKDOWN_KEYS,
)


# ---------------------------------------------------------------------------
# Resume scoring
# ---------------------------------------------------------------------------
def _complete_resume_payload(**overrides):
    payload = {
        "summary": "A solid resume.",
        "score_breakdown": {
            "content_completeness": 20, "quantified_achievements": 15,
            "skills_relevance": 22, "formatting_clarity": 18,
        },
        "resume_score": 999,  # deliberately wrong - must be ignored in favor of the breakdown sum
        "technical_skills": ["Python"], "soft_skills": [], "education": [],
        "projects_experience": [], "strengths": [], "weaknesses": [],
        "missing_information": [], "improvement_suggestions": [],
        "ats_suggestions": [], "formatting_suggestions": [],
    }
    payload.update(overrides)
    return payload


def test_resume_score_is_computed_from_breakdown_sum_not_model_total():
    result = _validate_resume_analysis(_complete_resume_payload())
    assert result is not None
    assert result["resume_score"] == 20 + 15 + 22 + 18 == 75
    assert result["resume_score"] != 999


def test_resume_analysis_rejects_missing_summary():
    payload = _complete_resume_payload()
    del payload["summary"]
    assert _validate_resume_analysis(payload) is None


def test_resume_analysis_rejects_empty_summary():
    payload = _complete_resume_payload(summary="   ")
    assert _validate_resume_analysis(payload) is None


def test_resume_analysis_rejects_missing_score_breakdown():
    payload = _complete_resume_payload()
    del payload["score_breakdown"]
    assert _validate_resume_analysis(payload) is None


def test_resume_analysis_rejects_incomplete_breakdown():
    for missing_key in REQUIRED_BREAKDOWN_KEYS:
        payload = _complete_resume_payload()
        del payload["score_breakdown"][missing_key]
        assert _validate_resume_analysis(payload) is None, f"should reject when {missing_key} is missing"


def test_resume_analysis_rejects_non_numeric_breakdown_value():
    payload = _complete_resume_payload()
    payload["score_breakdown"]["content_completeness"] = "not a number"
    assert _validate_resume_analysis(payload) is None


def test_resume_analysis_clamps_out_of_range_sub_scores():
    payload = _complete_resume_payload()
    payload["score_breakdown"]["content_completeness"] = 999   # way over 25
    payload["score_breakdown"]["quantified_achievements"] = -50  # way under 0
    result = _validate_resume_analysis(payload)
    assert result is not None
    assert result["score_breakdown"]["content_completeness"] == 25
    assert result["score_breakdown"]["quantified_achievements"] == 0


def test_resume_analysis_not_a_dict_rejected():
    assert _validate_resume_analysis(None) is None
    assert _validate_resume_analysis("just a string") is None
    assert _validate_resume_analysis([1, 2, 3]) is None


def test_resume_analysis_missing_optional_lists_default_to_empty_not_rejected():
    """Optional descriptive fields (strengths, weaknesses, etc.) are NOT
    scores - a response missing them is still usable, just thinner."""
    payload = _complete_resume_payload()
    del payload["strengths"]
    del payload["ats_suggestions"]
    result = _validate_resume_analysis(payload)
    assert result is not None
    assert result["strengths"] == []
    assert result["ats_suggestions"] == []


# ---------------------------------------------------------------------------
# Hybrid matching
# ---------------------------------------------------------------------------
def test_match_weights_sum_to_one_and_match_documented_values():
    assert abs(sum(MATCH_WEIGHTS.values()) - 1.0) < 1e-9
    assert MATCH_WEIGHTS == {"skill_overlap": 0.35, "resume_similarity": 0.15, "semantic_fit": 0.50}


def test_skill_overlap_percent_full_match():
    assert _skill_overlap_percent(["Python", "React", "SQL"], ["Python", "React"]) == 100.0


def test_skill_overlap_percent_partial_match_case_insensitive():
    # 1 of 2 required skills present, case/whitespace-insensitive match
    result = _skill_overlap_percent(["python "], [" Python", "Django"])
    assert result == 50.0


def test_skill_overlap_percent_no_required_skills_is_100():
    assert _skill_overlap_percent(["Python"], []) == 100.0


def test_skill_overlap_percent_zero_match():
    assert _skill_overlap_percent(["Java"], ["Python", "React"]) == 0.0


def test_resume_similarity_percent_counts_keyword_hits():
    resume_text = "Experienced in Python and Flask development."
    result = _resume_similarity_percent(resume_text, ["Python", "Flask", "React"])
    assert result == round(2 / 3 * 100, 1)


def test_resume_similarity_percent_empty_resume_is_zero():
    assert _resume_similarity_percent("", ["Python"]) == 0.0
    assert _resume_similarity_percent(None, ["Python"]) == 0.0


def test_validate_match_result_combines_with_documented_weights():
    data = {
        "matching_skills": ["Python"], "missing_skills": ["React"],
        "semantic_fit_score": 80, "explanation": "Good fit.", "suggestions": [],
    }
    result = _validate_match_result(data, skill_overlap=60.0, resume_similarity=40.0)
    expected = round(0.35 * 60.0 + 0.15 * 40.0 + 0.50 * 80)
    assert result["match_score"] == expected
    assert result["score_breakdown"]["skill_overlap_percent"] == 60.0
    assert result["score_breakdown"]["resume_similarity_percent"] == 40.0
    assert result["score_breakdown"]["semantic_fit_score"] == 80
    assert result["score_breakdown"]["weights"] == MATCH_WEIGHTS


def test_validate_match_result_clamps_semantic_score_and_handles_bad_input():
    data = {"semantic_fit_score": 500}  # way out of range
    result = _validate_match_result(data, skill_overlap=0.0, resume_similarity=0.0)
    assert result["score_breakdown"]["semantic_fit_score"] == 100

    data_bad = {"semantic_fit_score": "not a number"}
    result_bad = _validate_match_result(data_bad, skill_overlap=0.0, resume_similarity=0.0)
    assert result_bad["score_breakdown"]["semantic_fit_score"] == 0


def test_validate_match_result_rejects_non_dict():
    assert _validate_match_result(None, 0, 0) is None
    assert _validate_match_result("oops", 0, 0) is None
