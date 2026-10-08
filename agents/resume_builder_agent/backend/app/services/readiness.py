"""Phase 2 readiness skill: how job-ready the learner's resume is.

Score: the best ATS score among the learner's analysed resumes (0-100). A
resume that was built but never analysed has no score yet; the summary says
so, so the readiness view can suggest running an ATS check.
"""
from ..models import AtsAnalysis, Resume, User


def _texts(value, limit=3):
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("requirement") or item.get("text") or item.get("title") or item.get("name")
        if item:
            result.append(str(item)[:160])
        if len(result) == limit:
            break
    return result


def student_summary(user_id):
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    user = User.query.filter_by(user_id=user_id).first() if user_id else None
    if user is None:
        return empty
    resumes = Resume.query.filter_by(user_id=user.user_id).all()
    if not resumes:
        return empty
    analyses = (AtsAnalysis.query.filter_by(user_id=user_id)
                .order_by(AtsAnalysis.final_score.desc(), AtsAnalysis.created_at.desc()).all())
    best = analyses[0] if analyses else None
    scored = [r.ats_score for r in resumes if r.ats_score is not None]
    score = best.final_score if best else (max(scored) if scored else None)
    times = [r.updated_at or r.created_at for r in resumes] + [a.created_at for a in analyses]
    last = max((t for t in times if t), default=None)
    gaps = _texts(best.missing_requirements) if best else []
    if score is None:
        gaps = ["Run an ATS check on your resume"]
    return {
        "schema": "digidara.student_summary.v1",
        "score": float(score) if score is not None else None,
        "activity_count": len(resumes) + len(analyses),
        "last_activity_at": last.isoformat() if last else None,
        "strengths": _texts(best.matched_requirements) if best else [],
        "gaps": gaps,
        "metrics": {
            "resumes": len(resumes),
            "ats_checks": len(analyses),
            "best_job_match": max((r.job_match_score for r in resumes if r.job_match_score is not None), default=None),
            "downloads": sum(r.download_count or 0 for r in resumes),
        },
    }
